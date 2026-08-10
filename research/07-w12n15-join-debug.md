# W12-N15 Wi-Fi Join Failure — Root Cause (tool side)

**Status:** ROOT CAUSE IDENTIFIED (2026-08-09) · **Researcher:** Nebula
**Symptom:** `--setup-wifi` reports *"Wi-Fi credentials accepted by bulb"* + *"saved for
XX:XX:XX:XX:XX:XX"*, then **"[✗] Bulb did not contact required endpoints."** Add-on log shows
**zero** endpoint hits, **no your IoT VLAN DHCP lease ever**, bulb **reverts to SoftAP**. Twice.

---

## VERDICT

**The wizard's two success messages are FALSE POSITIVES. Nothing was ever confirmed.** There is
no contradiction to explain — the tool never verified anything, so "accepted then failed" is not
a paradox, it is the expected output when a bulb **silently ignores** the provisioning packet.

**Is SengledTools provisioning viable for the W12-N15?** — **Unproven, not disproven.** The
payload is chip-agnostic JSON+RC4, so nothing about it is *inherently* invalid for an
RTL8710BN. But the tool has only ever been validated on **W31-N15/W31-N11 (ESP8266)**, and the
run was made in **non-interactive mode, which skips the one step that would have told us
anything**. **Do not conclude the W12-N15 is unprovisionable yet — the decisive test hasn't
been run.** See §5.

---

## 1. 🔴 "Wi-Fi credentials accepted by bulb" is printed even when the bulb says NOTHING

`sengled/wifi_setup.py`, the credential send:

```python
    encrypted_params = encrypt_wifi_payload(params_payload)
    s.sendto(encrypted_params.encode("utf-8"), (BULB_IP, BULB_PORT))
    try:
        data, _ = s.recvfrom(4096)
        ...
        if response_json.get("payload", {}).get("result") is not True:
            warn_("Bulb rejected credentials (plaintext error."); return None, None
        ...
            if not ... decrypted_resp.get("payload", {}).get("result"):
                warn_("Bulb rejected credentials (decryption failed)."); return None, None
    except socket.timeout:
        pass                      # <-- TOTAL SILENCE FROM THE BULB
    success("Wi-Fi credentials accepted by bulb", extra_indent=6)   # <-- printed anyway
```

**`except socket.timeout: pass` falls straight through to the success message.** The only paths
that *prevent* it are an **explicit** rejection. A bulb that receives a packet it cannot decrypt
or does not understand simply drops it — producing exactly this output.

> **Read the message as: "we sent a packet and were not explicitly told no."**
> It carries **zero** evidence the bulb parsed the payload, accepted the SSID, or even
> understood the protocol.

## 2. 🔴 "Wi-Fi credentials saved for <MAC>" is about the TOOL, not the bulb

```python
    save_bulb(bulb_mac, lan_ip)
    success(f"Wi-Fi credentials saved for {bulb_mac}", extra_indent=6)
```

`save_bulb()` writes to **SengledTools' own local state file**. It is the tool remembering the
MAC. **It says nothing about the bulb's NVS/flash.** Both "successes" in the field report are
hollow — which is consistent with, not contradicted by, no DHCP lease.

## 3. 🔴 Non-interactive mode SKIPS the bulb's own Wi-Fi scan — the step that would diagnose this

The AP-scan exchange is **gated behind `if interactive:`**:

```python
    if interactive:
        ...
        scan_req = {"name": "scanWifiRequest",  ...}
        ap_req   = {"name": "getAPListRequest", ...}
```

- **Interactive:** the bulb scans and returns *its own* visible AP list; the operator picks from
  it. This **proves the bulb can see the SSID** before any credentials are sent, and captures
  the **BSSID**.
- **Non-interactive (`--ssid`/`--password`, what was run):** no scan at all. The SSID is
  **blind-pushed**. The code even says so:
  ```python
    wifi_bssid = None  # BSSID is not available in non-interactive mode.
  ```
  and for an ASCII SSID it sends `{"ssid": ..., "password": ...}` with **no BSSID**.

**So the run never established that the bulb can see `YOUR_IOT_SSID` at all.**

## 4. 🔴 The bulb's actual reply is only printed in INTERACTIVE mode — `-v` is NOT enough

```python
    if interactive: debug(f"Sending unencrypted payload:\n{...}")
    if interactive: debug(f"Received raw response from bulb:\n{response_str}")
```

These are gated on **`interactive`**, *not* on `is_verbose()`. **Running non-interactively with
verbose will still hide the one piece of evidence that matters.** This is why both runs produced
no usable diagnostic.

## 5. ✅ THE DECISIVE TEST — run it interactively, next attempt

```
python3 sengled_tool.py --setup-wifi \
    --http-server-ip YOUR_LEASED_IP --http-port 57542 \
    --broker-ip YOUR_LEASED_IP --broker-port 18883
```
**Omit `--ssid` and `--password`** so the wizard goes interactive. Then read three things:

| Observation | Meaning |
|---|---|
| **(a) Bulb returns an AP list at all?** | No list ⇒ the bulb isn't speaking this protocol (or the RC4 key/schema differs on W12-N15) ⇒ **tool-side incompatibility**, §6. |
| **(b) Does `YOUR_IOT_SSID` appear in the bulb's list?** | Absent ⇒ **RF/AP-side problem**, not the tool: wrong band, hidden SSID, no 2.4 GHz on the nearest AP. |
| **(c) Real response to `setParamsRequest` (`payload.result: true`)?** | A genuine `true` ⇒ creds truly accepted ⇒ failure is at association/DHCP ⇒ §7. Silence ⇒ confirms §1. |

**This single run splits the three candidate causes apart.** Nothing else should be attempted
before it.

## 6. Is the payload ESP8266-specific? — **No, but it is W31-specific in provenance**

- The provisioning payload is **application-layer JSON**, RC4-encrypted then base64'd
  (`sengled/crypto.py`), sent over UDP to `192.168.8.1:9080`. **Nothing in that format is
  CPU-architecture dependent** — unlike `shim.bin`, which genuinely *is* Xtensa machine code.
- **But** the RC4 key is a **single hardcoded constant** lifted from the Sengled app:
  ```python
  KEY_STR = "MTlCaWppbmdTaGFuZ2hhaVdpU2VuZ2xlZEZpMjBBQUJBU0U2NA=="
  ```
  and the whole flow was validated only against **W31-N15 / W31-N11**. If the W12-N15's
  MXCHIP/RTL8710BN firmware uses a **different key, a different field schema, or a different
  message name**, the bulb decrypts to garbage and **drops the packet silently** — reproducing
  the exact observed behaviour (timeout → false "accepted" → no join → SoftAP revert).
- **This is the leading tool-side hypothesis, and §5(a)/(c) tests it directly.**

## 7. If the bulb DOES answer properly, look at the AP — RTL8710BN is fussy

No DHCP lease ⇒ the bulb most likely never associated. Check on the AP serving `YOUR_IOT_SSID`:

1. **WPA3 / WPA2-WPA3 mixed mode** — 🔴 **prime suspect.** RTL8710BN-class radios are
   **WPA2-PSK/CCMP only**. A mixed-mode SSID commonly lets a device "accept" credentials and
   then fail association silently. **Set WPA2-PSK (CCMP/AES) only** for a test.
2. **PMF (802.11w) = required** — same failure mode. Set to *optional* or *disabled*.
3. **Band** — bulb is **2.4 GHz only**. Confirm the nearest AP actually offers `YOUR_IOT_SSID` on
   2.4 GHz and isn't 5 GHz-only or band-steering aggressively.
4. **Hidden SSID** — non-interactive mode sends **no BSSID**, so a hidden SSID is unlikely to
   work. Interactive (§5) captures the BSSID.
5. **PSK charset/length** — verify no shell-mangling of `***` in the password argument (quote it).

## 8. ✅ The MQTT port mismatch is MOOT for this failure — confirmed structurally

The wizard logged `Using external MQTT broker: YOUR_LEASED_IP:8883` while the add-on listens on
**18883**. **This cannot explain the join failure**, and the reasoning is structural, not a guess:

- The provisioning payload contains **only** `userID`, `appServerDomain`, `jbalancerDomain`,
  `timeZone`, `routerInfo`. **There is no broker address in it.**
- The broker host/port are handed to `SetupServer(mqtt_host, mqtt_port, preferred_port)` and
  served **later**, over HTTP, from **`/jbalancer/new/bimqtt`** — an endpoint the bulb can only
  reach **after** it has joined Wi-Fi.
- The bulb never joined, so it never fetched the broker address. The port was never used.

⚠️ **But fix it anyway for the next run** — it will break the moment the join succeeds, because
`8883` is only the default (`DEFAULT_BROKER_PORT`/`BROKER_TLS_PORT`). **Pass
`--broker-port 18883` explicitly.** The team lead's instinct ("moot") was correct.

## 9. Loose end worth a glance — the reported MAC

`XX:XX:XX:XX:XX:XX` does **not** match the `B0:CE:18` (Zhejiang Shenghui / Sengled) OUI recorded
in `the project state notes` for this product family. Two innocuous explanations (SoftAP interface MAC differs
from the STA MAC; or a second registered OUI), but if it is a **placeholder/garbage MAC** that
would itself be evidence for §6 — i.e. the tool mis-parsing a response it doesn't actually
understand. **Cheap check:** compare against the MAC printed on the bulb/box, and against what
the AP sees during an association attempt.

## 10. Answer to the question as asked

> *Is SengledTools provisioning viable for the W12-N15 at all, and if not, what specifically
> breaks for RTL8710BN?*

- **Not yet answerable — and the two runs so far contain no evidence either way**, because both
  "success" messages are unconditional (§1, §2) and non-interactive mode suppresses every
  diagnostic (§3, §4).
- **Nothing is known to be architecturally broken for RTL8710BN in the *provisioning* path.**
  That path is JSON+RC4 over UDP and is CPU-agnostic. (This is *unlike* the flashing path, which
  is genuinely ESP8266-only because `shim.bin` is Xtensa code — do not conflate the two.)
- **The realistic failure candidates, in order:**
  1. **RC4 key / message-schema mismatch** on W12-N15 firmware → silent drop (§6).
  2. **AP-side association failure** — WPA3/mixed mode or PMF-required against a WPA2-only
     radio (§7).
  3. Bulb cannot see the SSID (band/hidden) (§7.3–4).
- **Run §5 before drawing any conclusion.** It costs one interactive attempt and discriminates
  all three.

## Upstream issue search — no prior art

`HamzaETTH/SengledTools` issues matching W12-N15 / WF864 / MX1290 / RTL8710 / "credentials
accepted but won't connect" / SoftAP-revert: **none**. Only #62 (out-of-box activation, closed)
and #10 (MQTT SSL, closed) surface. **Nobody has publicly reported provisioning a W12-N15** —
consistent with the README listing it as an untested, non-flashable model. If §5 shows the bulb
ignoring the protocol, that is a genuinely new finding worth filing upstream.

**Status: root cause identified (instrumentation false-positive); device-side cause pending §5.**

---
---

# ⚠️ §11 — PRIOR-ART CORRECTION (the priorart investigation, 2026-08-09, later same day)

**§10 and the "no prior art" section above are WRONG on one decisive point, and it changes
the hypothesis ranking.** The §1–§4 code analysis is correct and stands — this only overturns
the *external evidence* claims. Issue **#62 was dismissed as "out-of-box activation, closed"
without reading its body**; it is in fact a **W12-N15 provisioning report with our exact
symptom**, and its author **wrote the fix**.

## 11.1 ✅ A W12-N15 HAS been successfully provisioned — this is now PROVEN, not "unproven"

**PR #63** (author **toolboc**, **merged 2026-06-05T03:18:08Z**), verbatim:

> *"Tested against **W12-N15** bulbs on stock firmware: handshake completes,
> `/life2/device/accessCloud.json` POST fires, **credentials persist across power cycles**."*

Closes `Fixes #60` / `Fixes #62`. **Issue #62** (toolboc, W12-N15) reported precisely our
shape — *"WiFi settings do not persist … once powered off they revert to factory reset"* — but
crucially also: *"**it is possible to operate with HomeAssistant integration during the setup
while it is connected to the home Wifi**."*

**⇒ Supersedes §10's "Not yet answerable" and the header's "Unproven, not disproven."
SengledTools provisioning is PROVEN VIABLE on the W12-N15.**

## 11.2 🔻 §6 (RC4 key / schema mismatch) is now the WEAKEST hypothesis, not the leading one

§6 reasoned that W12-N15 firmware might use a different RC4 key or schema, decrypt to garbage,
and drop the packet silently. That is now **directly contradicted**: in #62 a **W12-N15 parsed
the provisioning payload, joined the home WiFi, and was controllable from Home Assistant.**
The hardcoded `KEY_STR` and message schema **do work on this model**.

§6's *mechanism* remains a valid description of how a silent drop would look — but the
device-class premise is disproven. **Demote it.**

## 11.3 🔻 §7 (WPA3 / PMF / association) also weakens — and is not chip-correlated

Two independent reasons to demote:

1. **In both #60 and #62 the bulb associated.** #62's bulb reached the home network and was
   HA-controllable. An association-layer cause doesn't fit a bulb that associated.
2. **The identical failure happens on the *supported ESP8266* model.** In **#60**, user
   **GoldenDemon101** reports this exact failure on a **W31-N15** — the WF863/ESP8266EX bulb
   the tool was *validated* on — and reports it **still failing after PR #63 merged**.
   **#60 is still OPEN.**

> **Provisioning failure is not correlated with chip.** "It's the RTL8710BN" is not supported
> by any external evidence. Keep §7's WPA2-only/PMF checks — they're cheap — but they are no
> longer prime suspects.

On the vendor-doc question specifically: I found **no** documented class of RTL8710BN/AmebaZ
802.11r-or-PMF association failures. Realtek's own WiFi roaming doc lists **RTL8721Dx / RTL8710E
/ RTL8720E** and **does not list RTL8710B/AmebaZ at all**, and never mentions 802.11w/PMF. 11r
is a menuconfig opt-in, so a shipped bulb almost certainly has it off. The one spec-level
certainty (inference, not an observed bug): **a non-PMF client cannot join a PMF=*required*
BSS** — so verifying PMF is *optional* is still worth the 30 seconds.

## 11.4 ✅ We already have PR #63 — verified in our working tree, do not re-apply

Local HEAD `7d5eadb` is **2026-06-04 23:22:13 −0400**. That looks older than the 2026-06-05
merge but **is not** — the merge stamp is UTC (`03:18:08Z` = `23:18:08 −0400`), so our HEAD is
**4 minutes after it**. Confirmed by reading the source, not by date arithmetic alone:

- `sengled/mqtt_broker.py:279` → `ctx.set_alpn_protocols(["x-amzn-mqtt-ca", "mqtt"])`
- `sengled/mqtt_broker.py:258,269` → `DEFAULT:@SECLEVEL=0` · `:273` → `set_ecdh_curve("prime256v1")`
- `sengled/mqtt_broker.py:37-52` → cert-SAN-vs-current-LAN-IP check + regeneration

What PR #63 actually fixed (all in the broker's TLS path, none in the radio path):
**(1)** missing **ALPN** `x-amzn-mqtt-ca` → mbedtls aborted the handshake; **(2)** TLS1.2 +
narrow ciphers rejected by modern OpenSSL `SECLEVEL=2`; **(3)** **stale server-cert SAN** —
when the host LAN IP changed, `generate_certificates` **skipped regeneration because the files
existed**, so the bulb's cert check failed **silently** and pairing stalled at
*"Waiting for bulb to verify setup endpoints."*

## 11.5 ⚠️ SUPERSEDED by the network-side findings below — callback reachability is the *next* blocker, not this one

> **Correction to my own hypothesis (added after reading the network-side section, §"NETWORK-SIDE
> INVESTIGATION").** The live evidence there — bulb associates, completes the WPA2 4-way
> handshake, receives a valid `DHCPOFFER`, and **never sends `DHCPREQUEST`** — means the bulb
> **never obtains an IP**. It therefore never reaches the stage where it would call back to
> `:57542` / `:18883` at all. **My cross-VLAN reachability hypothesis below is not the current
> fault.** Deprioritise it now.
>
> It is not wrong, only *downstream*: once DHCP is fixed and the bulb holds a your IoT VLAN lease, the
> callback from your IoT VLAN → the tool host on VLAN 6 becomes the **very next thing that must work**.
> Keep steps 2–4 of the ordered list below on the shelf for that moment — especially advertising
> a reachable `--http-server-ip` and clearing stale certs.
>
> ### ⭐ And a corroboration the option-119 hypothesis gains from the prior art
> The network-side leading hypothesis is that your IoT VLAN's **DHCP option 119 (`domain-search`, RFC
> 3397, three domains)** is unparseable by the bulb's lwIP DHCP client. **PR #63's successful
> W12-N15 provisioning is a natural control for exactly that.** In #60's log the reporter's host
> sits on `YOUR_LAN_IP` — a stock consumer subnet, the kind of network that ships **only** the
> default DHCP options (3/6/1/51), **no option 119**. toolboc's W12-N15 took a lease and
> persisted credentials there.
>
> **So the one environment where a W12-N15 is documented to work is also an environment almost
> certainly free of option 119, while ours carries it.** That is independent support for the
> option-119 theory, and it upgrades it from "plausible embedded-stack limitation" to "the one
> variable that differs between the known-good case and ours." **Test A (drop option 119) is the
> right next move**, and if it works it is worth reporting upstream on #60.

### (original hypothesis, retained for the record) callback reachability, your IoT VLAN → VLAN 6

`sengled/utils.py:14-23`:
```python
s.connect(("8.8.8.8", 80)); local_ip = s.getsockname()[0]
```
Default-route detection — **it returns whichever interface holds the default route**, with no
notion of which VLAN the bulb will land on. That IP is baked into the callback URLs. From
**#60's verbose log** (mirrored locally):

```
"appServerDomain": "http://YOUR_LAN_IP:57542/life2/device/accessCloud.json",
"jbalancerDomain": "http://YOUR_LAN_IP:57542/jbalancer/new/bimqtt"
[✓] Wi-Fi credentials accepted by bulb
[✓] Wi-Fi credentials saved for XX:XX:XX:XX:XX:XX
[✗] Wi-Fi setup failed: Bulb did not contact required endpoints.
```
…and, in the same run, `[✓] MQTT broker running on 192.168.8.2:8883` — the **bulb-AP-side**
address, because the host was still joined to the bulb's SoftAP at that moment, while the
advertised callback used the home IP. **Which IP lands where is genuinely fragile in this tool.**

**Why this is the prime suspect here:** after accepting creds the bulb leaves the SoftAP, joins
the IoT SSID (**your IoT VLAN**), and must call back to the host on **:57542/tcp** and the broker on
**:18883/tcp**. The tool host (`the workstation`) is on **VLAN 6**. So the bulb must route
**your IoT VLAN → VLAN 6** to two high ports — and **"IoT VLAN cannot reach the trusted VLAN" is the
single most standard homelab firewall rule.** It would produce exactly this failure while every
"did the bulb take the credentials?" check looks fine.

⚠️ **Caveat, stated honestly:** JP's symptom is *worse* than #62's. #62's bulb **got a lease and
worked during setup**, failing only to *persist*. Ours reportedly **never took a your IoT VLAN DHCP
lease at all**. So #62 proves the model *can* be provisioned; it does **not** prove ours is the
same fault. The closest symptom match is **#60** — still open, and on an ESP8266 bulb.
Combined with §1's false-positive finding, "no lease" + "accepted" is consistent with the packet
never being acted on **or** with the callback being unreachable; §5's interactive run
discriminates, so **§5 remains the right next step.**

### Ordered checks (revised, cheapest first)
1. **§5's interactive run** — unchanged and still first. It's the only step that yields real evidence.
2. **Advertise an IP the bulb can reach** — run from a host with a your IoT VLAN leg, or pass
   `--http-server-ip` / `--broker-ip` explicitly (HA has a your IoT VLAN leg at `YOUR_LEASED_IP`).
   Don't trust `get_local_ip()` on a multi-VLAN host.
3. **Open your IoT VLAN → host `:57542/tcp` and `:18883/tcp`** on the router for the pairing window,
   then remove. Verify with a listener; don't assume.
4. **Delete the existing certs** so the SAN regenerates against the IP actually advertised —
   #60's log still shows `Certificates already exist, skipping generation`, and a stale SAN
   fails **silently**. This is PR #63's weakest link resurfacing operationally.
5. **Then** the AP: PMF *optional* not required, WPA2-PSK/CCMP only, 2.4 GHz confirmed.
6. Keep `--broker-port 18883` explicit (§8 — correct, and still correct).

## 11.6 Evidence mirrored locally

`<your-workspace>/prior-art/evidence-w12n15/`

| File | Contents |
|---|---|
| `pr-63-the-fix.md` | PR #63 body, author, exact merge timestamp — the W12-N15 success claim |
| `pr-63.diff` | full 147-line diff (`sengled/mqtt_broker.py`) |
| `issue-62.md` | W12-N15 "reverts to factory reset" + maintainer reply |
| `issue-60.md` | "Stuck at Verification Step" **+ full `--verbose` failure log** — closest match to our symptom; **OPEN** |

## 11.7 Search coverage (so nobody repeats it)

All **33 issues** and **34 PRs** fetched via the API and grepped **locally** — not keyword-searched
through the API, which is what missed #62's body the first time. Hits:
`W12` → 1 (#62) · `WF864` → 0 · `MX1290` → 0 · `RTL8710` → 0 · `EMW3091` → 0 ·
`credential` → 3 (#31, #48, #51) · `revert` → 1 (#62).
**No issue names WF864, MX1290, or RTL8710 anywhere** — so the earlier "no prior art" conclusion
was reached by searching for the *chip* names, which genuinely return nothing. The prior art is
filed under the **model** (#62) and the **fix** (#63).

**Revised status:** provisioning **proven viable** on W12-N15 upstream · we already carry the fix ·
chip-class theories demoted · prime suspect is **cross-VLAN callback reachability** · **§5 still
the decisive next action.**

---

# NETWORK-SIDE INVESTIGATION — Nebula (read-only) — 2026-08-09 23:0x PDT

**Scope:** strictly read-only. I changed nothing on the router or any AP.
**Result: the starting hypothesis is REFUTED, and the actual root cause is captured below.
It is NOT a Wi-Fi problem, and NOT a network-config problem.**

## 🚨 HEADLINE — the premise was wrong on two counts

1. **"Never associates with `YOUR_IOT_SSID`" is FALSE.** The bulb associates fine, and completes
   the full WPA2 4-way handshake.
2. **The DHCP server answers correctly and instantly. The BULB ignores the offer.**
   It sends `DHCPDISCOVER`, gets a valid `DHCPOFFER`, and **never sends `DHCPREQUEST`** —
   over and over — then gives up at ~16 s and reverts to SoftAP.

**The failure is inside the bulb's DHCP client. Every network element did its job.**

## Evidence 1 — hostapd on `north-office` (YOUR_LAN_IP), bulb `XX:XX:XX:XX:XX:XX`
```
IEEE 802.11: authenticated
IEEE 802.11: associated (aid 16)
AP-STA-CONNECTED XX:XX:XX:XX:XX:XX auth_alg=open
WPA: pairwise key handshake completed (RSN)
EAPOL-4WAY-HS-COMPLETED XX:XX:XX:XX:XX:XX
   ... ~16 s later ...
AP-STA-DISCONNECTED XX:XX:XX:XX:XX:XX
```
This cycle repeats (21:21, 21:26 ×3, 22:52 ×3). Interface is **`phy1-ap1`**, which is the
**`YOUR_IOT_SSID`** BSS (2nd BSS on the 2.4 GHz radio — note `wireless.radio0` maps to `phy1` at
runtime, so `phy1-ap1` = YOUR_IOT_SSID, confirmed against the generated hostapd conf).

⇒ **Association works. `auth_alg=open`. The PSK is CORRECT — the 4-way handshake completes.**
This eliminates every credential theory, every 802.11r/PMF theory, and every "cheap chip can't
associate" theory in one shot.

## Evidence 2 — dnsmasq on the router — 🎯 THE ACTUAL FAULT
```
22:52:55 DHCPDISCOVER(br-lan.8) XX:XX:XX:XX:XX:XX
22:52:55 DHCPOFFER(br-lan.8)   YOUR_LEASED_IP XX:XX:XX:XX:XX:XX
22:52:55 DHCPDISCOVER(br-lan.8) XX:XX:XX:XX:XX:XX
22:52:55 DHCPOFFER(br-lan.8)   YOUR_LEASED_IP XX:XX:XX:XX:XX:XX
   ... this repeats 10+ times across 14 seconds ...
```
**There is never a `DHCPREQUEST`. There is never a `DHCPACK`.**
The DHCP exchange is DISCOVER → OFFER → REQUEST → ACK; the bulb aborts after OFFER.

- ✅ your IoT VLAN bridging works (`br-lan.8`) — offers reach the client's segment
- ✅ Server responds in <1 s, every time, with a valid address (`YOUR_LEASED_IP`)
- ✅ Pool is healthy: `start=100 limit=150` (YOUR_LEASED_IP–.249), **92 leases, 58 free** — not exhaustion
- ❌ Bulb never accepts the offer ⇒ no lease ⇒ firmware times out ~16 s ⇒ back to SoftAP

## Hypothesis testing — what I checked and what it showed

| Hypothesis (from brief) | Verdict | Evidence |
|---|---|---|
| 802.11r / fast roaming breaks it | ❌ **REFUTED** | `ieee80211r='0'` on **all 9** YOUR_IOT_SSID APs; runtime `wpa_key_mgmt=WPA-PSK` only (no `FT-PSK`) |
| 802.11k / v | ❌ **REFUTED** | unset on all 9 APs |
| PMF (`ieee80211w`) required | ❌ **REFUTED** | unset on all 9; **no `ieee80211w` line in the generated hostapd conf** for YOUR_IOT_SSID |
| WPA3 / SAE / mixed mode | ❌ **REFUTED** | `encryption='psk2'` → runtime `wpa=2`, `wpa_pairwise=CCMP` |
| Dual-band same-SSID / band steering | ❌ **REFUTED** | YOUR_IOT_SSID is **2.4 GHz-only** on every AP |
| DHCP pool exhausted | ❌ **REFUTED** | 58 addresses free |
| Association failure | ❌ **REFUTED** | it associates; 4-way handshake completes |

**the router has no radios** — it is a Dell OptiPlex 7050 x86 OpenWrt router with no
`/etc/config/wireless`. The Wi-Fi is a fleet of **9 independent OpenWrt APs**, mixed hardware
(TP-Link OnHub, ASUS OnHub, EAP225-Outdoor, Netgear WNDR4300SW, Extreme WS-AP3825i ×2,
Linksys WRT1900AC / EA6350v3), each with its own `YOUR_IOT_SSID` BSS on 2.4 GHz, channels 1/6/11.

### Fleet-wide `YOUR_IOT_SSID` config (read-only sweep, all APs)
| AP | Model | radio | band | ch | enc | 11r | 11w | 11k/v |
|---|---|---|---|---|---|---|---|---|
| YOUR_LAN_IP | TP-Link OnHub | radio0 | 2g | 6 | psk2 | 0 | unset | unset |
| YOUR_LAN_IP | ASUS OnHub | radio1 | 2g | 1 | psk2 | 0 | unset | unset |
| YOUR_LAN_IP | EAP225-Outdoor v1 | radio1 | 2g | 11 | psk2 | 0 | unset | unset |
| YOUR_LAN_IP | Netgear WNDR4300SW | radio0 | 2g | 11 | psk2 | 0 | unset | unset |
| YOUR_LAN_IP | Extreme WS-AP3825i | radio1 | 2g | 11 | psk2 | 0 | unset | unset |
| YOUR_LAN_IP | ASUS OnHub | radio0 | 2g | 1 | psk2 | 0 | unset | unset |
| YOUR_LAN_IP | Linksys WRT1900AC v1 | radio0 | 2g | 6 | psk2 | 0 | unset | unset |
| YOUR_LAN_IP | Extreme WS-AP3825i | radio1 | 2g | 1 | psk2 | 0 | unset | unset |
| YOUR_LAN_IP | Linksys EA6350v3 | radio0 | 2g | 11 | psk2 | 0 | unset | unset |
| YOUR_LAN_IP | Linksys MR8300 | — | — | — | — | — | — | does **not** broadcast YOUR_IOT_SSID |

**No config drift.** Runtime hostapd for YOUR_IOT_SSID: `wpa=2`, `wpa_pairwise=CCMP`,
`wpa_key_mgmt=WPA-PSK`, `auth_algs=1`, `okc=0`, **no `ieee80211w`**. By contrast the site's other SSIDs do use those features — one runs
`WPA-PSK FT-PSK WPA-PSK-SHA256` + `ieee80211w=1`, another `WPA-PSK FT-PSK`. The IoT SSID
deliberately does not, which is why the association theories never had anything to bite on.

> ### ⛔ DO NOT BUILD THE PROPOSED TEST SSID
> The brief asked me to recommend a minimal SSID: *WPA2-PSK, no 11r/k/v, `ieee80211w` disabled,
> 2.4 GHz, single AP.* **`YOUR_IOT_SSID` is already exactly that** (bar "single AP"). Creating a new
> SSID would reproduce the current config under a new name and change nothing. It would cost an
> evening and disprove nothing.

## 🎯 LEADING ROOT-CAUSE HYPOTHESIS — an oversized/unparseable DHCP OFFER

The bulb receives the OFFER and discards it. The most likely reason is the **contents** of the
offer. your IoT VLAN's DHCP config carries a non-default option set:

```
dhcp.iot.dhcp_option='3,YOUR_LEASED_IP' '6,YOUR_LEASED_IP' 'option:domain-search,lan,example.lan,example.net'
```

`option:domain-search` is **DHCP option 119 (RFC 3397)**, which uses compressed domain-name
encoding and here carries **three** domains. Options 3 and 6 are tiny and universal; **option
119 is the unusual, bulky one.**

Minimal embedded DHCP clients — notably the **lwIP stack used on Realtek Ameba / RTL8710BN** —
are known to have small receive buffers and limited option parsers, and to silently drop offers
they cannot parse. **"Repeated DISCOVER, valid OFFER, never a REQUEST" is the classic signature
of an offer the client received but could not accept.**

This also explains the contrast cleanly: the **AiDot bulb (different silicon/stack) got
YOUR_LEASED_IP with no trouble**, as did dozens of ESP-based devices on the same VLAN and SSID.
Whatever is wrong is specific to this firmware's DHCP client, not to the network.

## ✅ RECOMMENDED MINIMAL TEST — a proposal for JP, NOT applied by me

**Do not create a new SSID.** Instead make the DHCP offer lean and retry provisioning.

**Test A (smallest, reversible, ~30 s) — drop option 119 from your IoT VLAN:**
```sh
# on the router — REMOVES ONLY the domain-search option from the iot pool
uci show dhcp.iot.dhcp_option                 # record current value first
uci del_list dhcp.iot.dhcp_option='option:domain-search,lan,example.lan,example.net'
uci commit dhcp && /etc/init.d/dnsmasq restart
```
Impact: your IoT VLAN clients lose DNS *search-suffix* convenience only. Routing and DNS still work
(options 3 and 6 are untouched). Fully reversible with `uci add_list`.
Then re-run provisioning and watch for **`DHCPREQUEST` + `DHCPACK`**:
```sh
ssh root@YOUR_ROUTER_IP 'logread -f | grep -i "b0:ce:18"'
```

**Test B (if A fails) — hand the bulb a static lease** so it can skip discovery entirely, and
confirm whether it will talk at all with a known address.

**Test C (diagnostic, no change) — packet-level truth.** Capture on the router to see the exact
offer the bulb rejects:
```sh
ssh root@YOUR_ROUTER_IP 'tcpdump -i br-lan.8 -n -s0 -vv port 67 or port 68'
```
Read the OFFER's total length and option list. If it is near/over a small buffer bound, that
confirms the hypothesis outright.

**Success criterion for all three: a `DHCPREQUEST` followed by `DHCPACK` in the dnsmasq log.**
Until that appears, nothing else about the bulb's provisioning can be judged.

## 🤝 Handoff to the ota investigation (tool-side half)
The evidence **moves the problem off the network entirely** — but note it may *not* be
tool-side either, since the bulb fails at plain DHCP, before any Sengled protocol runs.
Two things worth checking on the tool side anyway:
1. The bulb never reaching an IP means the `appServerDomain` / `jbalancerDomain` values handed
   to it are moot **for this failure** — don't chase them until DHCP completes.
2. Once a lease appears, the next thing to verify is whether those URLs (built from
   `get_local_ip()` while the workstation sat on the bulb's 192.168.8.x SoftAP) are still reachable from
   your IoT VLAN — a 192.168.8.x server address would be unreachable at YOUR_LEASED_IP and would produce a
   *second*, similar-looking give-up.

*Security note: AP PSKs were visible during this inspection and are deliberately NOT recorded
here — this tree is slated to become a public repo.*

## ADDENDUM — the two remaining network variables, answered directly

**Q: PMF / `ieee80211w` — is it `required`/`2`?**
**A: No. It is absent entirely = disabled.**
- uci: `ieee80211w` **unset** on all 9 `YOUR_IOT_SSID` BSSes (contrast `admin_2g`, which explicitly sets `ieee80211w='1'` — so the fleet does use PMF where intended, just not here).
- Runtime hostapd: **no `ieee80211w` line in the YOUR_IOT_SSID BSS block.** Not "optional", not "required" — not present.

**Q: WPA mode — pure WPA2-PSK, or WPA2/WPA3-mixed / SAE?**
**A: Pure WPA2-PSK.** Runtime: `wpa=2`, `wpa_pairwise=CCMP`, `wpa_key_mgmt=WPA-PSK`. No `sae`, no `wpa=3`, no mixed mode, no `WPA-PSK-SHA256`.

Verification coverage: **uci on 9/9** APs; **runtime hostapd on 4** (YOUR_LAN_IP, .102, .246, .135) — the other five didn't expose a hostapd conf under `/var/run` or `/tmp`. Importantly, **the AP the bulb actually connects to (YOUR_LAN_IP north-office) is runtime-verified**, so for the failure in question this is definitive.

⇒ **Both remaining network variables are benign. The network is NOT the cause.** Confirmed, and the router itself has no wireless config at all (no radios).

### ⚠️ But "not the network" ≠ "it's the provisioning tool"
The bulb fails at **plain DHCP**, before any Sengled/SengledTools protocol runs: it gets a valid `DHCPOFFER` and never sends `DHCPREQUEST`. No SengledTools code path is involved at that point. Handing this to the tool-side owner as "therefore it's provisioning" would send them hunting in the wrong file.

**The open item is Test A** (drop DHCP option 119 / `option:domain-search` from the `iot` pool) — the only proposal that targets the observed failure.

---

# §11. DHCPOFFER received, no DHCPREQUEST — RTL8710BN / Ameba-Z lwIP analysis (2026-08-09)

New field data: option 119 removed, **still** DHCPOFFER → silence. No lease.

## 11.1 *** THE MECHANISM — lwIP has exactly one way to do this ***

In lwIP, an OFFER that arrives and produces **no** DHCPREQUEST has essentially a single cause.
`dhcp_handle_offer()` is guarded:

```c
static void dhcp_handle_offer(struct netif *netif, struct dhcp_msg *msg_in)
{
  /* obtain the server address */
  if (dhcp_option_given(dhcp, DHCP_OPTION_IDX_SERVER_ID)) {
      ...
      ip4_addr_copy(dhcp->offered_ip_addr, msg_in->yiaddr);
      dhcp_select(netif);          /* <-- the ONLY path that sends DHCPREQUEST */
  } else {
      LWIP_DEBUGF(..., ("dhcp_handle_offer(netif=%p) did not get server ID!\n", ...));
      /* falls through, does nothing, no retry */
  }
}
```

> **If lwIP does not have DHCP option 54 (Server Identifier) *registered from its own parse*,
> it silently drops the OFFER and never sends a REQUEST.** No error on the wire, no retry — it
> just waits, times out, and (for the bulb) reverts to SoftAP. **That is precisely our symptom.**

dnsmasq **always** sends option 54 — so this is almost certainly **not** a missing option. It is
**`dhcp_parse_reply()` failing to reach or record option 54.** That reframes the whole fix:

> ### The goal is not "remove the option that breaks it".
> ### The goal is **make the option block small and simple enough that lwIP's parser survives
> ### long enough to register option 54.**

Why the parse aborts, in order of likelihood on a Realtek Ameba SDK (an old, vendor-patched
lwIP — the Realtek stack is separately documented as buggy here; e.g. *enabling
`LWIP_NETIF_HOSTNAME` in Realtek lwIP is known to break DHCP negotiation*):

1. **Option block spans/overflows the parser's working buffer.** lwIP's DHCP option
   handling is sized around `DHCP_OPTIONS_LEN` (**default 68 bytes**, `DHCP_MIN_OPTIONS_LEN`).
   A modern OpenWrt OFFER easily exceeds that. Vendor-patched 1.4.x-era parsers abort or
   truncate rather than skip cleanly.
2. **Options arriving after the abort point are simply never registered** — so whether 54 is
   seen is a function of *how far into the block it sits*, i.e. of total option volume.
3. **Option overload (option 52) / `sname`+`file` field reuse** — a classic weak spot in
   cut-down parsers.
4. **pbuf boundary** — a long OFFER split across pbufs; `pbuf_copy_partial` returns short and
   parsing bails.

**Corollary that matters for the capture:** stripping options is not superstition — every byte
removed moves option 54 earlier and shrinks the block toward the 68-byte comfort zone.

## 11.2 🔴 SECOND, INDEPENDENT HYPOTHESIS — the broadcast flag

Worth ruling out *first* because it is cheap and would explain everything:

**If the bulb sets the BROADCAST flag (`flags = 0x8000`) in its DHCPDISCOVER but dnsmasq replies
by unicast**, the bulb may never actually ingest the OFFER — even though your capture clearly
shows a valid OFFER on the wire. Capture-on-the-AP ≠ received-by-the-client.

**Diagnostic (do this in the capture):** read `bootp.flags` in the bulb's **DISCOVER**.
- `0x8000` (broadcast requested) + a **unicast** OFFER (dst = the offered IP, not 255.255.255.255)
  ⇒ **this is your bug**, and §11.5 fixes it in one line.
- `0x0000` ⇒ broadcast flag is not the issue; go to §11.3/11.4.

## 11.3 *** FIRST, READ THE BULB'S OWN PARAMETER REQUEST LIST (option 55) ***

This is the highest-value single datum in the capture, and it should be read **before** changing
any config:

- dnsmasq, by default, **only sends options the client asked for** in its **option 55 (PRL)**,
  plus a small mandatory set. So a bloated OFFER means either (a) the bulb requested a lot, or
  (b) something is **force**-sending options.
- **Capture `dhcp.option.request_list_item` from the DISCOVER.** If the bulb requests only
  1/3/6/51/54, then a large OFFER means options are being force-fed — and the fix is to stop
  forcing them, not to blanket-strip.
- Also record the **total OFFER size** and the **byte offset of option 54** within the option
  block. If 54 sits late (after 119/121/15/6), §11.1's ordering theory is directly confirmed.

## 11.4 Ranked strip-list — what to remove from the OFFER, highest value first

**Never strip:** **53** (message type), **54** (server ID — the whole point), **51** (lease
time). Keep **1** (subnet mask) and **3** (router) — small, and the bulb needs them to be useful.

| Rank | Option | Why | Typical bytes |
|---|---|---|---|
| **1** | **121** + **249** classless static routes | **Biggest single offender.** Variable-length, often tens of bytes, and Microsoft's 249 duplicates 121. A bulb needs neither. | 10–60+ |
| **2** | **119** domain search | Already removed — **keep it removed**, it was correct, just not sufficient. | 10–40 |
| **3** | **6** DNS servers — *reduce to ONE* | 4 bytes per server. Don't suppress entirely (the bulb must resolve nothing, but a zero-length list can upset parsers); pin a single resolver. | 4–12 |
| **4** | **15** domain name | Pure padding for a bulb. | 5–20 |
| **5** | **252** WPAD / **44–47** NetBIOS / **42** NTP | Never needed by a bulb; strip on principle. | 4–30 |
| **6** | **58** renewal (T1) + **59** rebinding (T2) | Optional; lwIP derives sane defaults from option 51. | 12 |
| **7** | **28** broadcast address | Derivable from mask; safe to drop. | 6 |
| **8** | **12** hostname / **81** FQDN | Only if present. | var |

**Target:** get the total option block **under ~64 bytes**, i.e. inside `DHCP_MIN_OPTIONS_LEN`.
That is the threshold worth aiming at, not an arbitrary "less is better".

## 11.5 Exact OpenWrt config — per-MAC, leaves every other your IoT VLAN device untouched

dnsmasq suppresses an option when it is listed **with no value**. OpenWrt exposes this via a
`config tag` section, applied per-host by MAC. **Nothing here changes the offer any other client
receives.**

```sh
# /etc/config/dhcp  — via UCI

# 1) A tag carrying the strip-list (bare option numbers = SUPPRESS)
uci -q delete dhcp.sengled
uci set dhcp.sengled=tag
uci add_list dhcp.sengled.dhcp_option='121'   # classless static routes
uci add_list dhcp.sengled.dhcp_option='249'   # MS classless static routes
uci add_list dhcp.sengled.dhcp_option='119'   # domain search
uci add_list dhcp.sengled.dhcp_option='15'    # domain name
uci add_list dhcp.sengled.dhcp_option='252'   # wpad
uci add_list dhcp.sengled.dhcp_option='42'    # ntp
uci add_list dhcp.sengled.dhcp_option='44'    # netbios ns
uci add_list dhcp.sengled.dhcp_option='45'    # netbios dd
uci add_list dhcp.sengled.dhcp_option='46'    # netbios node type
uci add_list dhcp.sengled.dhcp_option='47'    # netbios scope
uci add_list dhcp.sengled.dhcp_option='58'    # T1 renewal
uci add_list dhcp.sengled.dhcp_option='59'    # T2 rebinding
uci add_list dhcp.sengled.dhcp_option='28'    # broadcast address
# keep DNS but to a SINGLE server (replace with the your IoT VLAN gateway):
uci add_list dhcp.sengled.dhcp_option='6,YOUR_LEASED_IP'

# 2) Bind the tag to just this bulb, with a fixed lease
uci -q delete dhcp.sengled_bulb1
uci set dhcp.sengled_bulb1=host
uci set dhcp.sengled_bulb1.name='sengled-bulb1'
uci add_list dhcp.sengled_bulb1.mac='XX:XX:XX:XX:XX:XX'
uci set dhcp.sengled_bulb1.ip='YOUR_LEASED_IP'
uci set dhcp.sengled_bulb1.tag='sengled'

uci commit dhcp
/etc/init.d/dnsmasq restart
```

**Then re-capture.** Compare the new OFFER's total option-block length and the offset of
option 54 against the baseline.

### If §11.2 says the broadcast flag is the problem

`dhcp-broadcast` is tag-aware but has no UCI mapping, so add it as a raw dnsmasq directive
(keeps the change scoped to the tag, not the whole VLAN):

```sh
mkdir -p /etc/dnsmasq.d
echo 'dhcp-broadcast=tag:sengled' > /etc/dnsmasq.d/sengled.conf
uci set dhcp.@dnsmasq[0].confdir='/etc/dnsmasq.d'
uci commit dhcp && /etc/init.d/dnsmasq restart
```
This forces **broadcast** replies **only** to tagged MACs. Cheap, reversible, and it is the
single highest-yield experiment if the DISCOVER carries `flags=0x8000`.

## 11.6 Suggested experiment order (cheapest discriminator first)

1. **Read the capture** — bulb's option-55 PRL, `bootp.flags` in DISCOVER, OFFER unicast vs
   broadcast, total option-block size, byte-offset of option 54. *(No config change.)*
2. **If `flags=0x8000` + unicast OFFER** → apply `dhcp-broadcast=tag:sengled` alone. Retest.
3. **Else** apply the §11.5 strip-tag. Retest. Note the new option-54 offset.
4. **Still failing?** Bisect: strip to the bare legal minimum (53, 54, 51, 1, 3 only) — if *that*
   works, re-add options one at a time to identify the exact poison. If even the minimal offer
   fails, the problem is **not** option content and the next suspects are §7's association-layer
   issues (WPA3/mixed-mode, PMF) — note that a client which never truly associated can still
   appear to "DHCP" if you are capturing at the AP rather than on the wire behind it.

## 11.7 SengledTools issue #60 — same symptom, no DHCP clues, still open

Re-read in full. Reporter: *"Nothing happens after this step 'Waiting for bulb to verify setup
endpoints…'"* — the laptop leaves the SoftAP and rejoins home Wi-Fi, then the verification hangs
**exactly** as ours does. **Open, unresolved, no maintainer response, no comments.**

- **No** mention of DHCP, leases, IP, or router/AP configuration. **No bulb model given.**
- Value: it establishes that **"stalls at verification" is a recurring, unexplained failure
  mode** — not unique to the W12-N15 and not obviously chip-specific.
- ⚠️ It does **not** corroborate the DHCP theory; it is a symptom match only. Do not over-read it.
- If our capture nails the mechanism, **#60 is the place to post it** — it would be the first
  concrete root-cause on that thread, and would also settle whether that reporter's bulb is the
  same chip family.

## 11.8 Handoff to the chipid investigation (capture checklist)

Capture on the AP/bridge for your IoT VLAN, filter `port 67 or port 68`, during one join attempt:

- [ ] **DISCOVER**: `bootp.flags` (0x8000?) · option 55 PRL contents · client MAC (confirm it is
      `XX:XX:XX:XX:XX:XX`, and whether that matches the bulb's printed MAC — see §9)
- [ ] **OFFER**: unicast or broadcast? · total frame length · **full option list in order** ·
      **byte offset of option 54** · presence of option 52 (overload)
- [ ] **Absence check**: confirm no REQUEST at all (vs. a REQUEST that goes unanswered — a very
      different bug)
- [ ] Whether the bulb re-DISCOVERs (retry loop) or goes straight back to SoftAP, and after how
      long

**Status: mechanism identified (lwIP drops OFFER when option 54 isn't registered); awaiting
capture to choose between broadcast-flag and option-bloat.**

---
---

# §12 — PRIOR ART for "associates, gets OFFER, never REQUESTs" (the priorart investigation, 2026-08-09)

Real-world reports of this exact symptom class on cheap IoT WiFi devices, **with the fixes that
actually worked**, ranked. Plus two corrections to §11.5/§11.2 and one negative result that saves
a dead end. Evidence mirrored to `prior-art/evidence-w12n15/`.

> **Headline: the single best-documented cause of this exact failure signature is not DHCP at all
> — it is WMM/802.11n.** It explains why association and the 4-way handshake succeed while the
> *first real data frames* (DHCP) fail, and it explains why removing option 119 changed nothing.

## 12.1 ⭐ RANK 1 — WMM / 802.11n data-frame incompatibility

`esp8266/Arduino` **#8412** + **#8299** are a large, well-documented instance of our signature:
devices associate, then **"the device ignores the DHCP offer from the router"** — confirmed by
**router-side packet traces**, not guesswork.

**The fix, independently confirmed by five+ reporters,** was forcing the client out of 802.11n:
```cpp
WiFi.setPhyMode(WIFI_PHY_MODE_11G);   // "worked like a charm" · "solved the issue for me"
```
**And the root cause, from `1d4rk` who found the workaround (verbatim):**

> *"The problem was due to the older ESP8266 Arduino core, starting from 2.6.0, that **disabled
> WMM/WME support in 802.11n mode** and it was added in the last release (because it is based on
> Espressif nonos_SDK 3.0.5). The connection is working good in 802.11n mode + WMM enabled (so no
> need to force 802.11g mode)."*

**Why this fits us better than any DHCP-content theory:**
**802.11n requires WMM/QoS.** A client that negotiates HT but mishandles WMM/QoS data frames will
still complete **management frames** (auth/assoc) and **EAPOL** (the 4-way handshake) — then fail
on the **first QoS-framed data exchange**, which is DHCP. That is *precisely* our staging:

| Stage | Frame type | Our result |
|---|---|---|
| auth / assoc | management | ✅ |
| WPA2 4-way | EAPOL | ✅ |
| **DHCP** | **QoS data** | ❌ **fails here** |
| → 16 s timeout, disconnect | | ❌ |

It also explains the **option-119 removal having no effect**: if the OFFER's *frames* aren't
getting through, its *contents* are irrelevant. And it's consistent with the AiDot bulb working —
different silicon, working WMM.

**AP-side test (JP controls this; the bulb's firmware is stock so the client-side fix is unavailable):**
on the AP serving the IoT SSID, for that BSS only:
```sh
# OpenWrt, on the AP (per-BSS, not per-radio where possible)
uci set wireless.<iface>.wmm='0'      # 11n requires WMM; disabling it drops the BSS to 11g behaviour
uci commit wireless && wifi reload
```
or force the radio to non-HT: `uci set wireless.<radio>.htmode='NONE'`.
⚠️ Scope it to the **one AP** you're pairing next to, and revert after — disabling WMM costs
throughput for every client on that BSS.

**Related, cheap, same family:** on ASUS gear, disabling **"Wi-Fi Agile Multiband" (802.11v)** on
2.4 GHz *"completely dissapeared"* the problem for reporter `movodos`. the chipid investigation verified
`ieee80211v` unset in UCI on all 9 APs — worth confirming it's also absent from the **runtime**
hostapd conf, since that's where it would actually bite.

## 12.2 ✅ CORRECTION to §11.5 — `dhcp-broadcast` *does* have a native UCI mapping

§11.5 states *"`dhcp-broadcast` is tag-aware but has no UCI mapping, so add it as a raw dnsmasq
directive."* **Not so** — OpenWrt has a first-class per-host boolean built for exactly this.
Verified in the packaged init script (mirrored as `evidence-w12n15/openwrt-dnsmasq.init`):

```sh
# line 1168 — passed UNCONDITIONALLY on every OpenWrt dnsmasq instance:
xappend "--dhcp-broadcast=tag:needs-broadcast"

# lines 406-411 — how a host earns that tag:
config_get_bool broadcast "$cfg" broadcast 0
[ "$broadcast" = "0" ] && broadcast= || broadcast=",set:needs-broadcast"
```

**So the whole fix is one UCI line on a host section — no confdir change, no raw file:**
```sh
uci set dhcp.sengled="host"
uci set dhcp.sengled.mac='XX:XX:XX:XX:XX:XX'
uci set dhcp.sengled.ip='YOUR_LEASED_IP'
uci set dhcp.sengled.broadcast='1'          # ← sets tag needs-broadcast; dnsmasq broadcasts to it
uci commit dhcp && /etc/init.d/dnsmasq restart
```
Prefer this over `confdir` + `/etc/dnsmasq.d/sengled.conf`: it's scoped to one MAC, survives
upgrades, is visible in LuCI, and doesn't repoint dnsmasq's include directory on the **main
firewall**. (The `extraconftext` UCI key, init line 1183, is the sanctioned escape hatch if a raw
directive is ever genuinely needed — still no need here.)

The fact that OpenWrt ships a dedicated `broadcast` flag per host is itself evidence: **"broken
DHCP client needs broadcast replies" is a common enough real-world failure to warrant a
purpose-built option.** §11.2's hypothesis is well-founded; only its plumbing was wrong.

## 12.3 ⛔ NEGATIVE RESULT — the *opposite* fix does not exist, don't hunt for it

There is a documented **mirror-image** failure: devices that **set the broadcast flag** but only
actually accept **unicast** (Honeywell Lyric thermostats, Sony TVs — dnsmasq-discuss 2019q2). The
reporter wrote a `--dhcp-unicast` patch and it fixed those devices.

**That option was never merged.** I checked the current dnsmasq man page: **`dhcp-unicast` → 0
occurrences**; `dhcp-broadcast` → 1. So if the capture shows the bulb *requesting* broadcast
(`flags=0x8000`) while dnsmasq already broadcasts, **there is no config-level lever left on the
dnsmasq side** — don't burn time looking for one. Escalate to §12.1 (WMM/11n) or §12.4 instead.

## 12.4 RANK 3 — AP driver / radio specific: just try a different AP

`kaloz/mwlwifi` **#278** — *"ESP8266/Embedded devices unable to connect to 2.4Ghz Radio"* — is our
signature almost line for line: devices **authenticate, complete the WPA key handshake, then fail
DHCP and get disconnected after ~30-40 s**. Marvell 88W8864 on OpenWrt.

**The reporter's resolution: the same device worked on a different radio of the same AP** ⇒
driver/radio-specific, not a general incompatibility.

**This is the cheapest discriminator available and needs zero config change.** JP has **9 APs of
mixed silicon**. The bulb was last seen on `north-office` (TP-Link OnHub, Qualcomm). **Retry
provisioning next to an AP with a different chipset** (e.g. an Extreme WS-AP3825i or the
EAP225-Outdoor) and see whether DHCP completes. If it does, everything above is moot.

## 12.5 RANK 4 — offer size / lwIP options buffer (corroborates §11's strip-list)

Independent support for the "offer too big" branch: lwIP's DHCP options buffer is a **compile-time
constant** with a floor of **68 bytes** (`DHCP_MIN_OPTIONS_LEN`), and **ESP-IDF added
`CONFIG_LWIP_DHCP_OPTIONS_LEN` specifically because servers send more options than the default
buffer holds** (`espressif/esp-idf@9e2f15a`). On stock bulb firmware that constant is **not
tunable**, so the only lever is making the server's OFFER smaller — exactly §11.4's strip-list.

Since **option 119 alone was not enough**, the remaining fat is options **15 (domain-name)**,
**28 (broadcast-address)**, **6 (multiple DNS servers)** and **42 (NTP)**. §11's approach of
stripping to the legal minimum (53, 54, 51, 1, 3) and re-adding one at a time remains correct;
this just confirms the mechanism is real and documents the 68-byte floor it's fighting.

## 12.6 ⚠️ A tension worth naming before you change anything

Fixes 12.1 and 12.2 pull in **opposite directions on broadcast reliability**:
- **12.2 forces the OFFER to be broadcast.** Broadcast/multicast frames are sent at the basic rate
  and are **buffered until the DTIM beacon** — so a client in power-save can *miss* them. Cheap
  IoT bulbs use aggressive power-save.
- **12.1 (disable WMM / drop to 11g)** removes the QoS/aggregation layer that most often breaks
  broadcast delivery to buggy clients in the first place.

They are therefore **complementary, not contradictory — but change ONE variable per attempt**, or
a success won't tell you which lever worked, and you'll leave a throughput-costing WMM change on
the AP forever for no reason.

## 12.7 Ranked action list (merging §11.6 with the above)

| # | Action | Cost | Why this rank |
|---|---|---|---|
| 0 | **Read the capture** — option-55 PRL, `bootp.flags`, OFFER unicast/broadcast, option-block size | none | §11.6 is right: no config change should precede this |
| 1 | **Retry next to a different-chipset AP** | none | 12.4; zero-risk, and a whole-hypothesis killer |
| 2 | **`option broadcast '1'` on a host section for the bulb MAC** | 1 UCI line, per-MAC | 12.2; native, reversible, matches the "OFFER logged, client re-DISCOVERs" signature |
| 3 | **Disable WMM (or `htmode=NONE`) on the one pairing AP's IoT BSS** | 1 UCI line on 1 AP | 12.1; **best explanation of the stage signature**, ranked below #1/#2 only because it costs throughput while set |
| 4 | **Strip options to the legal minimum, re-add one at a time** | several UCI edits | §11.4/12.5; option 119 alone already excluded |
| 5 | Don't chase `dhcp-unicast` | — | 12.3; not in mainline dnsmasq |

## 12.8 Evidence mirrored

| File in `prior-art/evidence-w12n15/` | Contents |
|---|---|
| `esp8266-8412-wmm-11g.md` | the WMM/802.11n root cause + `setPhyMode(11G)` fix, with confirmations |
| `esp8266-8299-ignores-offer.md` | "device ignores the DHCP offer" + router traces; ASUS Agile-Multiband fix |
| `openwrt-dnsmasq.init` | the packaged init script — proof of `broadcast` → `set:needs-broadcast` (L406-411, L1168) |
| `issue-60.md`, `issue-62.md`, `pr-63*.{md,diff}` | SengledTools provisioning prior art (§11 above) |

## 12.9 Honest limits of this section

- **No report anywhere names RTL8710BN/Ameba-Z specifically** for this symptom. Every analog above
  is ESP8266/lwIP or a generic "cheap IoT client." The **shared factor is lwIP + minimal WiFi
  stack**, which the Ameba SDK also uses — so the analogy is reasonable but it *is* an analogy.
- **12.1's mechanism is inference from a verified fact.** The WMM-in-11n root cause is quoted
  verbatim and the 11g fix is confirmed by multiple users; my mapping of it onto
  *"management ✅ / EAPOL ✅ / QoS-data ❌"* is my reasoning about frame classes, not a quote.
  The capture (12.7 step 0) can confirm or kill it: look for **QoS data frames** and retries
  around the OFFER.
- Nobody in any thread reports a **stock, unflashable** bulb fixed from the AP side alone. Ours
  cannot take a firmware fix, so the client-side remedies that worked for most reporters
  (`setPhyMode`, newer core, static IP via code) are **unavailable to us**. That asymmetry is why
  I rank the AP-side and DHCP-server-side levers above everything else.

---

# PACKET CAPTURE — the DHCP OFFER decoded (Nebula, 2026-08-09 23:2x PDT)

**My option-119 theory was WRONG.** The lead removed option 119; the bulb still fails. I captured
the live exchange on `br-lan.8` during a real pairing run and decoded it. Below is what is
actually on the wire, two red herrings I killed, and the one genuine protocol anomaly left.

Method: `tcpdump -i br-lan.8 -s0 -c 60 port 67 or port 68 -w /tmp/bulb-dhcp.pcap` on the router,
while I drove `sengled_tool.py --setup-wifi` from the workstation over the bulb's SoftAP. the workstation's Wi-Fi
was temporarily detached from its normal SSID and **restored afterwards**.

## The bulb's DISCOVER (verbatim)
```
XX:XX:XX:XX:XX:XX > XX:XX:XX:XX:XX:XX, length 410
0.0.0.0.68 > 255.255.255.255.67: BOOTP/DHCP, Request, length 368
xid 0xe153e4ce, Flags [none] (0x0000)        <<< BROADCAST FLAG *NOT* SET
DHCP-Message (53): Discover
MSZ (57): 1500                                <<< accepts up to 1500 bytes
Parameter-Request (55), length 4:
    Subnet-Mask (1), Default-Gateway (3), BR (28), Domain-Name-Server (6)
```

## Gatekeeper's OFFER (verbatim)
```
XX:XX:XX:XX:XX:XX > XX:XX:XX:XX:XX:XX, length 342
YOUR_LEASED_IP.67 > 255.255.255.255.68: BOOTP/DHCP, Reply, length 300
xid 0xe153e4ce, Flags [Broadcast] (0x8000)   <<< SERVER SET THE FLAG THE CLIENT CLEARED
Your-IP YOUR_LEASED_IP   Server-IP YOUR_LEASED_IP
DHCP-Message (53): Offer
Server-ID   (54): YOUR_LEASED_IP
Lease-Time  (51): 43200
RN (58): 21600 · RB (59): 37800
Subnet-Mask (1): 255.255.255.0
BR          (28): YOUR_LEASED_IP
DNS          (6): YOUR_LEASED_IP
Gateway      (3): YOUR_LEASED_IP
END + 8 PAD
```
**Offer size: 300-byte BOOTP payload, 342 bytes on the wire.** Nowhere near any limit, and the
client advertised MSZ 1500. It contains **exactly the four options the client asked for**, plus
the mandatory 53/54/51/58/59. **No option 119, no option 15 domain-name, no option overload.**
⇒ The lead's option-119 removal did land — it simply wasn't the cause. **Offer size/content is
fully exonerated.**

## ❌ Red herring 1 — "a second DHCP server at YOUR_LEASED_IP"
The offer comes from `YOUR_LEASED_IP`, not `YOUR_LEASED_IP`. That is **not** a rogue server:
```
br-lan.8:  inet YOUR_LEASED_IP/24                       <- the router's real address
           inet YOUR_LEASED_IP/24 secondary proto keepalived   <- the VRRP VIP
           link/ether XX:XX:XX:XX:XX:XX
```
Gatekeeper is `.3` on every VLAN and `.1` is the VRRP VIP (same pattern as YOUR_ROUTER_IP / YOUR_LAN_IP).
Serving from `.3` while handing out `.1` as gateway/DNS is correct and intentional.

## ❌ Red herring 2 — "bad udp cksum" in the capture
The capture flags `[bad udp cksum 0x1348 -> 0x5d5a!]`. That is a **TX-checksum-offload artifact**,
not corruption — verified:
```
br-lan.8   tx-checksumming: on
eth0/eth1  tx-checksumming: on
```
tcpdump taps before the NIC computes the checksum, so locally-generated packets always look bad
in a sender-side capture. The frame is correct on the wire. **Not the cause.**
*(Had offload been off, this would have been damning — worth checking rather than assuming.)*

## 🎯 THE ONE REAL ANOMALY — the server overrides the client's BROADCAST flag
- Client DISCOVER: **`Flags [none] (0x0000)`** — the bulb explicitly asks for a **unicast** reply.
- Server OFFER: **`Flags [Broadcast] (0x8000)`**, sent to `255.255.255.255` / `XX:XX:XX:XX:XX:XX`.

RFC 2131 §4.1 says the server should honour the client's BROADCAST flag. Here it is being
**forcibly overridden for every client on the router**, by a deliberate local customisation:

```
/etc/dnsmasq.user.d/broadcast.conf
    # Force broadcast OFFER/ACK for all clients to help WiFi clients
    # whose APs buffer unicasts during power save
    dhcp-broadcast              <<< bare, UNCONDITIONAL, applies to every client
```
(The uci-generated config has the properly *scoped* form `dhcp-broadcast=tag:needs-broadcast`;
the user.d file adds an unconditional one on top.)

### Why this is now the leading cause
1. **It is the only deviation from a textbook exchange left** — everything else in the offer is
   minimal, correct and exactly what the client requested.
2. **It is a non-default, hand-added local setting.** These bulbs demonstrably work on ordinary
   networks; when a device works everywhere else and fails here, the prime suspect is the thing
   this network does that others don't. This is precisely such a thing.
3. Minimal DHCP stacks (Realtek Ameba / lwIP class, which is what the RTL8710BN runs) are the
   ones most likely to be strict about the reply's framing when they cleared the flag.

**Honest caveat:** ~92 other your IoT VLAN devices get the same forced-broadcast treatment and are fine,
including the AiDot bulb. So this is stack-specific pickiness, not a blanket breakage — which is
why it is a *hypothesis to test*, not a proven cause. It is, however, the only candidate the
packets still support, and it is cheap to falsify.

## ✅ PROPOSED TEST — 30 seconds, reversible (NOT applied by me)
This mutates shared infrastructure affecting every your IoT VLAN client, so I have not run it.

**Test D — disable the forced broadcast and retry:**
```sh
ssh root@YOUR_ROUTER_IP 'mv /etc/dnsmasq.user.d/broadcast.conf /tmp/broadcast.conf.bak \
  && /etc/init.d/dnsmasq restart'
# retry pairing, then watch:
ssh root@YOUR_ROUTER_IP 'logread -f | grep -i "b0:ce:18"'
# revert:  mv /tmp/broadcast.conf.bak /etc/dnsmasq.user.d/ && /etc/init.d/dnsmasq restart
```
Other clients simply revert to standard RFC behaviour (unicast unless they ask for broadcast) —
what every other network does — so risk is low and the window is short.

**Success criterion: `DHCPREQUEST` followed by `DHCPACK`.**

### Permanent fix if Test D works — scoped, keeps power-save help for those who need it
Don't leave broadcast off globally. Make it opt-in and simply don't tag the Sengleds:
```
# /etc/dnsmasq.user.d/broadcast.conf
dhcp-broadcast=tag:needs-broadcast
```
```sh
# tag only the clients that actually needed forced broadcast
uci add dhcp host; uci set dhcp.@host[-1].mac='<mac-that-needs-it>'
uci add_list dhcp.@host[-1].tag='needs-broadcast'
```
The Sengleds are never tagged, so they receive a standards-compliant unicast OFFER, and the
power-save-sensitive devices keep the behaviour the file was written for.

## If Test D fails
The packets will have exonerated size, contents, options, server identity, checksums **and**
broadcast framing — i.e. the network will be fully cleared at the DHCP layer, and the remaining
explanation is a defect in the bulb's own DHCP client (e.g. it needs a specific option it didn't
request, or its 16 s window closes before its own retry logic completes). At that point the
pragmatic workaround is a **static DHCP reservation** for each Sengled MAC, plus testing whether
the bulb will accept an offer at all on a stock/simple network for comparison.

---

# ✅ TEST D RESULT — ROOT CAUSE PROVEN AND FIXED (2026-08-09 23:33 PDT)

## The W12-N15 only accepts a **UNICAST** DHCP OFFER. Forced broadcast was the bug.

Removed `/etc/dnsmasq.user.d/broadcast.conf` (the unconditional `dhcp-broadcast`), restarted
dnsmasq — verified it came back healthy — and re-paired. Result:

```
23:33:08 DHCPDISCOVER(br-lan.8) XX:XX:XX:XX:XX:XX
23:33:08 DHCPOFFER(br-lan.8)   YOUR_LEASED_IP XX:XX:XX:XX:XX:XX
23:33:08 DHCPREQUEST(br-lan.8) YOUR_LEASED_IP XX:XX:XX:XX:XX:XX      ← FIRST EVER
23:33:08 DHCPACK(br-lan.8)     YOUR_LEASED_IP XX:XX:XX:XX:XX:XX Sengled_WiFi_Color_W12-N15
```
```
LEASE: 1786386788 XX:XX:XX:XX:XX:XX YOUR_LEASED_IP Sengled_WiFi_Color_W12-N15
```

### Packet-level proof of mechanism
| | Before (broken) | After (working) |
|---|---|---|
| Client DISCOVER | `Flags [none] (0x0000)` | `Flags [none] (0x0000)` *(unchanged)* |
| Server OFFER dst | `255.255.255.255` (bcast) | **`YOUR_LEASED_IP` (unicast)** |
| Server OFFER flags | `Flags [Broadcast] (0x8000)` | **`Flags [none] (0x0000)`** |
| Client response | *(none — silent drop)* | **DHCPREQUEST → ACK** |

The only variable changed was the reply's framing. **The bulb clears the BROADCAST flag and
genuinely means it — it silently discards a broadcast OFFER.**

### Stability confirmed (the ~16 s disconnect loop is gone)
```
23:33:03 AP-STA-CONNECTED / EAPOL-4WAY-HS-COMPLETED
23:37:47 still associated — assoc_count=1, NO AP-STA-DISCONNECTED since
```
**4m45s+ continuously associated**, lease held. Previously it dropped at ~16 s every time. The
disconnect loop was a *symptom* of the DHCP failure, not an RF problem — exactly as the packets
predicted.

### Bulb reached the local provisioning server ✅
From the HA add-on log:
```
[✓] Served GET  on /jbalancer/new/bimqtt
[✓] Served POST on /life2/device/accessCloud.json
```
Both handshake endpoints hit. The bulb is on the network and talking to the local stack.

## 🎁 Bonus: the DHCP hostname settles a documentation error
The bulb identifies itself as **`Sengled_WiFi_Color_W12-N15`** — independently confirming both
the model (**W12-N15**, matching the project state notes) **and that it is the COLOR variant**.
`SengledTools`' compatibility matrix lists *"W12-N15 (WiFi **white** LED)"* — that is **wrong**,
and worth an upstream PR alongside the module correction.

## ⚠️ Remaining blocker — a DIFFERENT layer, not the network
```
HA broker connect failed (rc=5)      (repeating)
```
MQTT **CONNACK code 5 = "not authorized"**. This is the **add-on failing to authenticate to
HA's Mosquitto broker** — an add-on credential problem, entirely separate from the bulb. The
bulb→add-on HTTP handshake already succeeded. Owner: whoever holds the add-on config
(the ota investigation); fix the broker username/password.

## 🔧 Recommended permanent fix — surgical, keeps the power-save workaround
Test D is currently **left in place** (broadcast.conf parked at `/tmp/broadcast.conf.off`,
backup at `/tmp/broadcast.conf.bak`). Don't leave forced-broadcast globally disabled *or*
globally enabled — make it opt-in:

```
# /etc/dnsmasq.user.d/broadcast.conf
dhcp-broadcast=tag:needs-broadcast
```
```sh
# tag ONLY the power-save-sensitive clients that actually needed it
uci add dhcp host
uci set dhcp.@host[-1].mac='<mac-that-needs-broadcast>'
uci add_list dhcp.@host[-1].tag='needs-broadcast'
uci commit dhcp && /etc/init.d/dnsmasq restart
```
Sengleds stay untagged → standards-compliant unicast OFFER → they work.
*(Note `dhcp.lan.broadcast='1'` and `dhcp.lan.force='1'` also exist on the `lan` section —
review those separately; they don't affect your IoT VLAN.)*

**⚠️ Regression watch:** the original file's comment says forced broadcast was added to help
"WiFi clients whose APs buffer unicasts during power save." Some device on the network needed
that. Watch for a client that stops getting leases, and tag *that* MAC rather than reverting
globally.

## Final status of the no-solder Sengled path
**Unblocked at the network layer.** DHCP works, the bulb holds its association, and it completes
the local cloud handshake. What remains is the add-on's MQTT auth (rc=5) — a config fix, not a
hardware or network one. **No UART flashing is required for this.**
