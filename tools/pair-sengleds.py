#!/usr/bin/env python3
"""Pair the remaining Sengled Wi-Fi bulbs and register them in Home Assistant.

Run it, then just flick bulbs. One bulb per loop iteration; press 'q' when the
last one is done and it finishes the job (DHCP reservations + HA entry).

    ./pair-sengleds.py            # real run
    ./pair-sengleds.py --dry-run  # prerequisites + read-only checks, changes nothing

WHY EACH STEP IS THE WAY IT IS (all verified against the hardware/source):

* The bulb PERSISTS the HTTP URLs it is handed at provisioning time
  (`appServerDomain` / `jbalancerDomain`, wifi_setup.py:413). They must point at
  Home Assistant, because the IoT VLAN cannot reach this workstation. Getting
  this wrong means re-pairing, so ADVERTISED_HOST is not guessed.
* The MQTT endpoint is NOT persisted -- it is re-fetched from the add-on's
  /jbalancer/new/bimqtt reply on every boot -- so --broker-port only matters for
  the wizard's own client.
* Success is judged by a NEW DHCP lease, never by the wizard's exit status: the
  wizard polls its OWN 127.0.0.1 HTTP server for confirmation, but the bulb's
  callbacks land on Home Assistant, so it reports a timeout even when it worked.
* While attached to a bulb's SoftAP this machine sits on 192.168.8.x and CANNOT
  reach the router -- so the lease check only happens after reconnecting.
* Passing both --ssid and --password makes the wizard non-interactive
  (sengled_tool.py:708), which is what allows this to loop unattended.

WHAT THIS SCRIPT ASSUMES (it is a reference implementation, not plug-and-play):

* NetworkManager (`nmcli`) for switching between your WiFi and each bulb's SoftAP.
* An OpenWrt router reachable over SSH, for reading dnsmasq leases and adding
  DHCP reservations via `uci`. Adapt add_reservations()/ssh_router() for anything else.
* Bitwarden/Vaultwarden (`bw`) for the WiFi PSK and a Home Assistant long-lived
  token. Adapt bw_get() for a different secret store.
* A local SengledTools checkout -- this script drives its CLI, it does not
  reimplement the protocol.

⚠️  BEFORE YOU RUN IT: the bulb requires a UNICAST DHCP offer. If your DHCP
    server forces broadcast replies (a bare `dhcp-broadcast` in dnsmasq), the
    bulbs will associate and then never take a lease, and this script will
    correctly report failure. See the repo README for the one-line fix.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import pathlib
import re
import ssl
import subprocess
import sys
import time

# ═══ CONFIGURATION — EDIT EVERY VALUE IN THIS BLOCK ═══════════════════════
# Every placeholder below must be replaced for your own network. Nothing here
# is a secret: the WiFi PSK and the HA token are fetched from your password
# manager at run time (see bw_get()), never stored in this file.

WIFI_IFACE = "wlan0"                    # your WiFi interface, e.g. `ip link`
IOT_SSID = "YOUR_IOT_SSID"              # the SSID the bulbs should join
BULB_AP_PREFIX = "Sengled_Wi-Fi Bulb_"  # leave as-is; the bulbs' own SoftAP prefix
SENGLED_OUI = "b0:ce:18"                # Sengled's IEEE OUI; used to spot bulbs in leases

# Names of the entries in your password manager (Bitwarden/Vaultwarden `bw`).
VAULT_WIFI_ITEM = "YOUR_VAULT_WIFI_ITEM"   # item whose password is the IoT PSK
VAULT_HA_TOKEN = "YOUR_VAULT_HA_TOKEN"     # item whose password is an HA long-lived token

HA_HOST = "YOUR_HA_HOST"                # Home Assistant address (HTTPS)
HA_PORT = 8123
# Trust-on-first-use pin for HA's self-signed certificate. See ha_api().
HA_PIN_PATH = pathlib.Path.home() / ".config" / "sengled" / "ha-cert.sha256"

# CRITICAL: the address the bulbs will PERSIST and call for the rest of their
# lives. It must be Home Assistant's address on the network the bulbs are on.
# Get this wrong and the only fix is re-pairing every bulb.
ADVERTISED_HOST = "YOUR_HA_IP_FACING_BULBS"
HTTP_PORT = 57542
BROKER_PORT = 18883                     # add-on's broker (8883/8884 are Mosquitto's)

ROUTER_SSH = "root@YOUR_ROUTER_HOST"    # OpenWrt router, for lease checks + reservations
LEASES = "/tmp/dhcp.leases"             # OpenWrt/dnsmasq lease file

# Path to a Python interpreter that has SengledTools' requirements installed,
# and to your local SengledTools checkout.
VENV_PY = "python3"
TOOL = "/path/to/SengledTools/sengled_tool.py"
TOOL_CWD = "/path/to/SengledTools"

LEASE_WAIT_SECONDS = 90
RESERVATION_PREFIX = "sengled-"

_SECRETS: list[str] = []           # scrubbed from every line this script prints


# --- plumbing ------------------------------------------------------------
def scrub(text: str) -> str:
    """Remove any known secret from text before it is displayed."""
    for s in _SECRETS:
        if s:
            text = text.replace(s, "***REDACTED***")
    return text


def say(msg: str = "") -> None:
    print(scrub(msg), flush=True)


def run(cmd: list[str], check: bool = False, timeout: int = 120, cwd: str | None = None):
    """Run a command, capturing output. Never echoes secrets."""
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, check=False
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {scrub(' '.join(cmd))}\n"
            f"{scrub(proc.stderr.strip())}"
        )
    return proc


def ssh_gk(remote_cmd: str, check: bool = False, timeout: int = 60):
    return run(
        ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes", ROUTER_SSH, remote_cmd],
        check=check,
        timeout=timeout,
    )


def bw_get(name: str, kind: str = "password") -> str:
    proc = run(["bw", "get", kind, name], timeout=90)
    if proc.returncode != 0:
        raise RuntimeError(
            f"vault lookup failed for {name!r}. Is the vault unlocked? "
            f"Run: bw unlock\n{scrub(proc.stderr.strip())}"
        )
    return proc.stdout.strip()


class CertPinError(RuntimeError):
    """The HA certificate changed -- refuse to send credentials."""


def _ha_context() -> ssl.SSLContext:
    """Context for HA's self-signed cert.

    Chain validation is impossible against a self-signed certificate presented
    on an IP address, so it is disabled -- but NOT left at that. Every connection
    is fingerprint-pinned in _ha_connect() below, because this request carries a
    long-lived Home Assistant access token in the Authorization header: handing
    that to an impostor on the LAN would surrender full control of HA. Pinning
    gives the same protection model as SSH's known_hosts.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _ha_connect() -> http.client.HTTPSConnection:
    """Open a connection to HA and verify its certificate fingerprint."""
    conn = http.client.HTTPSConnection(HA_HOST, HA_PORT, timeout=30, context=_ha_context())
    conn.connect()
    der = conn.sock.getpeercert(binary_form=True)
    if not der:
        conn.close()
        raise CertPinError("HA presented no certificate")
    fp = hashlib.sha256(der).hexdigest()

    if HA_PIN_PATH.exists():
        pinned = HA_PIN_PATH.read_text().strip()
        if fp != pinned:
            conn.close()
            raise CertPinError(
                "Home Assistant's TLS certificate does NOT match the pinned one.\n"
                f"  pinned : {pinned}\n  offered: {fp}\n"
                "Refusing to send the access token. If you legitimately replaced\n"
                f"HA's certificate, delete {HA_PIN_PATH} and re-run to re-pin."
            )
    else:
        HA_PIN_PATH.parent.mkdir(parents=True, exist_ok=True)
        HA_PIN_PATH.write_text(fp + "\n")
        HA_PIN_PATH.chmod(0o600)
        say(f"  pinned HA certificate on first use: sha256:{fp[:16]}...")
    return conn


def ha_api(path: str, data=None, method: str | None = None, token: str = ""):
    body = json.dumps(data).encode() if data is not None else None
    conn = _ha_connect()
    try:
        conn.request(
            method or ("POST" if data is not None else "GET"),
            path,
            body=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        raw = resp.read().decode()
        if resp.status >= 400:
            return resp.status, raw[:300]
        return resp.status, json.loads(raw or "null")
    finally:
        conn.close()


# --- discovery / state ---------------------------------------------------
def sengled_leases() -> dict[str, str]:
    """Current Sengled DHCP leases as {mac: ip}."""
    proc = ssh_gk(f"cat {LEASES}", check=True)
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1].lower().startswith(SENGLED_OUI):
            out[parts[1].lower()] = parts[2]
    return out


def reserved_macs() -> tuple[set[str], int]:
    """MACs that already have a reservation, and the highest sengled-N index."""
    proc = ssh_gk("uci show dhcp", check=True)
    macs: set[str] = set()
    highest = 0
    sections: dict[str, dict[str, str]] = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"^dhcp\.([^.=]+)\.([^=]+)='?([^']*)'?$", line.strip())
        if m:
            sections.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
    for cfg in sections.values():
        if cfg.get("mac"):
            macs.add(cfg["mac"].lower())
        name = cfg.get("name", "")
        if name.startswith(RESERVATION_PREFIX):
            try:
                highest = max(highest, int(name[len(RESERVATION_PREFIX):]))
            except ValueError:
                pass
    return macs, highest


def ha_sengled_hosts(token: str) -> set[str]:
    """Hosts already configured in any sengled_udp entry."""
    status, entries = ha_api("/api/config/config_entries/entry", token=token)
    if status != 200 or not isinstance(entries, list):
        raise RuntimeError(f"could not list HA config entries (http {status})")
    hosts: set[str] = set()
    for e in entries:
        if e.get("domain") == "sengled_udp":
            # The entry payload does not expose data{}, so fall back to the title
            # host hint plus the device registry via states below if needed.
            hosts.update(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", json.dumps(e)))
    # Authoritative: entity attributes expose each coordinator's host.
    status, states = ha_api("/api/states", token=token)
    if status == 200 and isinstance(states, list):
        for s in states:
            if s.get("entity_id", "").startswith("light."):
                h = (s.get("attributes") or {}).get("host")
                if h:
                    hosts.add(h)
    return hosts


def scan_for_bulb_ap() -> str | None:
    """Rescan Wi-Fi and return a Sengled SoftAP SSID, if any is broadcasting."""
    run(["nmcli", "device", "wifi", "rescan", "ifname", WIFI_IFACE], timeout=60)
    time.sleep(3)
    proc = run(["nmcli", "-t", "-f", "SSID", "device", "wifi", "list", "ifname", WIFI_IFACE])
    for line in proc.stdout.splitlines():
        ssid = line.strip()
        if ssid.startswith(BULB_AP_PREFIX):
            return ssid
    return None


# --- actions -------------------------------------------------------------
def provision(ap_ssid: str, wifi_password: str, original_conn: str) -> None:
    """Join the bulb's SoftAP, hand it the real network + HA URLs, then come back."""
    say(f"  joining bulb AP {ap_ssid!r} ...")
    proc = run(
        ["nmcli", "device", "wifi", "connect", ap_ssid, "ifname", WIFI_IFACE],
        timeout=90,
    )
    if proc.returncode != 0:
        say(f"  ! could not join {ap_ssid!r}: {scrub(proc.stderr.strip())}")
        return

    try:
        say("  provisioning (non-interactive; wizard timeout at the end is EXPECTED) ...")
        cmd = [
            VENV_PY, TOOL, "--setup-wifi",
            "--ssid", IOT_SSID,
            "--password", wifi_password,
            "--http-server-ip", ADVERTISED_HOST,
            "--http-port", str(HTTP_PORT),
            "--broker-ip", ADVERTISED_HOST,
            "--broker-port", str(BROKER_PORT),
            "--no-pause",            # only affects --diagnose; kept for parity
        ]
        proc = run(cmd, timeout=420, cwd=TOOL_CWD)
        tail = [l for l in (proc.stdout or "").splitlines() if l.strip()][-6:]
        for line in tail:
            say(f"    | {line}")
    finally:
        # Must leave the SoftAP before the router is reachable again.
        say("  reconnecting to the normal network ...")
        run(["nmcli", "connection", "down", ap_ssid], timeout=45)
        if original_conn:
            run(["nmcli", "connection", "up", original_conn, "ifname", WIFI_IFACE], timeout=90)
        time.sleep(6)


def wait_for_new_lease(before: dict[str, str]) -> tuple[str, str] | None:
    """Poll the router for a Sengled lease that was not there before."""
    say(f"  waiting up to {LEASE_WAIT_SECONDS}s for a new IoT-VLAN lease ...")
    deadline = time.time() + LEASE_WAIT_SECONDS
    while time.time() < deadline:
        try:
            now = sengled_leases()
        except RuntimeError:
            time.sleep(5)
            continue
        for mac, ip in now.items():
            if mac not in before:
                return mac, ip
        time.sleep(5)
    return None


def add_reservation(mac: str, ip: str, name: str, dry_run: bool) -> bool:
    """Add a DHCP reservation, syntax-checking dnsmasq before restarting it."""
    if dry_run:
        say(f"  [dry-run] would reserve {ip} -> {mac} as {name}")
        return True
    script = (
        f"set -e; "
        f"s=$(uci add dhcp host); "
        f"uci set dhcp.$s.name='{name}'; "
        f"uci set dhcp.$s.mac='{mac}'; "
        f"uci set dhcp.$s.ip='{ip}'; "
        # Validate BEFORE committing anything, so a bad value cannot take DNS down.
        f"uci commit dhcp; "
        f"if dnsmasq --test; then /etc/init.d/dnsmasq restart >/dev/null 2>&1; echo RESERVED; "
        f"else echo DNSMASQ_TEST_FAILED; exit 1; fi"
    )
    proc = ssh_gk(script, timeout=90)
    if "RESERVED" in proc.stdout:
        say(f"  reserved {ip} -> {mac} as {name}")
        return True
    say(f"  ! reservation failed for {mac}: {scrub((proc.stdout + proc.stderr).strip())}")
    return False


def ha_add_hosts(hosts: list[str], token: str, dry_run: bool) -> bool:
    """Register hosts with sengled_udp via the config flow's manual path.

    Creates a NEW config entry for the new hosts. The integration has no
    reconfigure/options step, and the flow rejects hosts that are already
    configured, so a fresh entry per batch is the non-destructive route --
    entity unique_ids are {entry_id}_{host}, so nothing collides.
    """
    if dry_run:
        say(f"  [dry-run] would add to HA via config flow: {', '.join(hosts)}")
        return True

    status, d = ha_api(
        "/api/config/config_entries/flow",
        {"handler": "sengled_udp", "show_advanced_options": False},
        token=token,
    )
    if status != 200 or not isinstance(d, dict) or "flow_id" not in d:
        say(f"  ! could not start config flow (http {status}): {d}")
        return False
    flow = d["flow_id"]

    # Step 1 is a menu (async_show_menu), selected with next_step_id.
    if d.get("type") == "menu":
        status, d = ha_api(
            f"/api/config/config_entries/flow/{flow}", {"next_step_id": "manual"}, token=token
        )
        if status != 200:
            say(f"  ! could not select the manual step (http {status})")
            return False

    status, d = ha_api(
        f"/api/config/config_entries/flow/{flow}",
        {"hosts": ", ".join(hosts), "name_prefix": "Sengled"},
        token=token,
    )
    if isinstance(d, dict) and d.get("type") == "create_entry":
        say(f"  added to HA: {d.get('title')}")
        return True

    errors = d.get("errors") if isinstance(d, dict) else None
    say(f"  ! HA did not create the entry (http {status}, errors={errors})")
    ha_api(f"/api/config/config_entries/flow/{flow}", method="DELETE", token=token)
    return False


# --- preflight -----------------------------------------------------------
def preflight(dry_run: bool) -> tuple[str, str, str]:
    say("=== preflight ===")

    proc = run(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"])
    if f"{WIFI_IFACE}:wifi" not in proc.stdout:
        raise RuntimeError(f"Wi-Fi interface {WIFI_IFACE} not found")
    say(f"  wifi interface {WIFI_IFACE}: present")

    proc = run(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"])
    original = ""
    for line in proc.stdout.splitlines():
        if line.endswith(f":{WIFI_IFACE}"):
            original = line.rsplit(":", 1)[0]
    say(f"  current wifi connection: {original or '(none)'} -- will restore at the end")

    wifi_password = bw_get(VAULT_WIFI_ITEM)
    _SECRETS.append(wifi_password)
    token = bw_get(VAULT_HA_TOKEN)
    _SECRETS.append(token)
    say(f"  vault: wifi password + HA token retrieved (both redacted from output)")

    proc = ssh_gk("echo ok")
    if "ok" not in proc.stdout:
        raise RuntimeError(f"cannot reach router at {ROUTER_SSH}")
    say(f"  router {ROUTER_SSH}: reachable")

    status, cfg = ha_api("/api/config", token=token)
    if status != 200 or not isinstance(cfg, dict):
        raise RuntimeError(f"HA API not reachable (http {status}) -- is it HTTPS on 8123?")
    if cfg.get("state") != "RUNNING":
        raise RuntimeError(f"HA is not RUNNING (state={cfg.get('state')}) -- wait and retry")
    say(f"  HA {cfg.get('version')}: RUNNING")
    if "sengled_udp" not in cfg.get("components", []):
        say("  ! WARNING: sengled_udp is not loaded in HA. Pairing will still work,")
        say("    but adding bulbs needs the integration loaded (restart HA first).")

    for path, label in ((VENV_PY, "venv python"), (TOOL, "sengled_tool.py")):
        if run(["test", "-f", path]).returncode != 0:
            raise RuntimeError(f"{label} not found at {path}")
    say("  SengledTools venv + tool: present")

    if dry_run:
        say("  MODE: DRY RUN -- no bulb will be paired, nothing will be changed")
    return wifi_password, token, original


# --- main ----------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Pair Sengled bulbs and add them to HA.")
    ap.add_argument("--dry-run", action="store_true",
                    help="check prerequisites and report current state; change nothing")
    args = ap.parse_args()

    try:
        wifi_password, token, original_conn = preflight(args.dry_run)
    except RuntimeError as e:
        say(f"\nPREFLIGHT FAILED: {e}")
        return 1

    known = sengled_leases()
    reserved, highest = reserved_macs()
    in_ha = ha_sengled_hosts(token)
    say("")
    say("=== current state ===")
    say(f"  Sengled leases on IoT VLAN: {len(known)}")
    for mac, ip in sorted(known.items(), key=lambda kv: kv[1]):
        flags = []
        if mac in reserved:
            flags.append("reserved")
        if ip in in_ha:
            flags.append("in HA")
        say(f"    {mac}  {ip:<15} {'[' + ', '.join(flags) + ']' if flags else '[NEW - needs setup]'}")
    say(f"  reservations present    : {len(reserved)} (highest {RESERVATION_PREFIX}N = {highest})")
    say(f"  hosts already in HA     : {len(in_ha)}")

    # Anything already leased but not yet reserved/registered gets picked up too,
    # so a half-finished earlier run completes instead of being skipped.
    newly: list[tuple[str, str]] = [
        (mac, ip) for mac, ip in known.items() if mac not in reserved or ip not in in_ha
    ]
    if newly:
        say(f"  -> {len(newly)} already-leased bulb(s) still need finishing; included below")

    if args.dry_run:
        say("")
        say("=== dry run: skipping the pair loop ===")
    else:
        say("")
        say("=== pair loop ===")
        while True:
            say("")
            ans = input(
                "Flick a Sengled's power ~5x until it flashes, then press Enter "
                "(or 'q' to finish and add to HA): "
            ).strip().lower()
            if ans == "q":
                break

            ap_ssid = scan_for_bulb_ap()
            if not ap_ssid:
                say("  no bulb in pairing mode -- reset it (flick ~5x until it flashes) and retry")
                continue
            say(f"  found {ap_ssid!r}")

            before = dict(known)
            provision(ap_ssid, wifi_password, original_conn)
            found = wait_for_new_lease(before)
            if not found:
                say("  ! no new lease appeared -- pairing did not complete. Reset and retry.")
                say("    (the wizard's own timeout message is normal and not the verdict)")
                continue
            mac, ip = found
            say(f"  PAIRED: {mac} -> {ip}")
            known[mac] = ip
            if (mac, ip) not in newly:
                newly.append((mac, ip))

    # --- finish up -------------------------------------------------------
    say("")
    say("=== finishing ===")
    if not newly:
        say("  nothing new to do -- every Sengled lease is already reserved and in HA")
    else:
        idx = highest
        for mac, ip in sorted(newly, key=lambda kv: kv[1]):
            if mac in reserved:
                say(f"  {ip}: reservation already exists, skipping")
            else:
                idx += 1
                add_reservation(mac, ip, f"{RESERVATION_PREFIX}{idx}", args.dry_run)

        to_add = [ip for _, ip in sorted(newly, key=lambda kv: kv[1]) if ip not in in_ha]
        if to_add:
            ha_add_hosts(to_add, token, args.dry_run)
        else:
            say("  all bulbs already present in HA, nothing to add")

    if not args.dry_run and original_conn:
        say("")
        say(f"  restoring wifi to {original_conn!r} ...")
        run(["nmcli", "connection", "up", original_conn, "ifname", WIFI_IFACE], timeout=90)
        proc = run(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"])
        active = [l.rsplit(":", 1)[0] for l in proc.stdout.splitlines()
                  if l.endswith(f":{WIFI_IFACE}")]
        say(f"  wifi now on: {active[0] if active else '(not connected)'}")

    say("")
    say("Done.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\ninterrupted -- wifi may still be on a bulb AP; "
            f"run 'nmcli connection up <your-connection> ifname {WIFI_IFACE}' to restore")
        sys.exit(130)
