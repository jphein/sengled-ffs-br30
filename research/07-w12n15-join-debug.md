# W12-N15 Wi-Fi Join Failure — Root Cause (tool side)

**Status:** superseded in part — see the reconciliation note at the top of this file.
**Symptom:** `--setup-wifi` reports *"Wi-Fi credentials accepted by bulb"* + *"saved for
XX:XX:XX:XX:XX:XX"*, then **"[✗] Bulb did not contact required endpoints."** Add-on log shows
**zero** endpoint hits, **no IoT-VLAN DHCP lease ever**, bulb **reverts to SoftAP**. Twice.

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
    --http-server-ip YOUR_HA_IP --http-port 57542 \
    --broker-ip YOUR_HA_IP --broker-port 18883
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

The wizard logged `Using external MQTT broker: YOUR_HA_IP:8883` while the add-on listens on
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

# ⚠️ §11 — PRIOR-ART CORRECTION (prior-art review, 2026-08-09)

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
   `--http-server-ip` / `--broker-ip` explicitly (HA has a your IoT VLAN leg at `YOUR_HA_IP`).
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
22:52:55 DHCPOFFER(br-lan.8)   YOUR_LAN_IP XX:XX:XX:XX:XX:XX
22:52:55 DHCPDISCOVER(br-lan.8) XX:XX:XX:XX:XX:XX
22:52:55 DHCPOFFER(br-lan.8)   YOUR_LAN_IP XX:XX:XX:XX:XX:XX
   ... this repeats 10+ times across 14 seconds ...
```
**There is never a `DHCPREQUEST`. There is never a `DHCPACK`.**
The DHCP exchange is DISCOVER → OFFER → REQUEST → ACK; the bulb aborts after OFFER.

- ✅ your IoT VLAN bridging works (`br-lan.8`) — offers reach the client's segment
- ✅ Server responds in <1 s, every time, with a valid address (`YOUR_LAN_IP`)
- ✅ Pool is healthy: `start=100 limit=150` (YOUR_LAN_IP–.249), **92 leases, 58 free** — not exhaustion
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
`wpa_key_mgmt=WPA-PSK`, `auth_algs=1`, `okc=0`, **no `ieee80211w`**. By contrast `admin` runs
`WPA-PSK FT-PSK WPA-PSK-SHA256` + `ieee80211w=1`, and `roam` runs `WPA-PSK FT-PSK`.

> ### ⛔ DO NOT BUILD THE PROPOSED TEST SSID
> The brief asked me to recommend a minimal SSID: *WPA2-PSK, no 11r/k/v, `ieee80211w` disabled,
> 2.4 GHz, single AP.* **`YOUR_IOT_SSID` is already exactly that** (bar "single AP"). Creating a new
> SSID would reproduce the current config under a new name and change nothing. It would cost an
> evening and disprove nothing.

## 🎯 LEADING ROOT-CAUSE HYPOTHESIS — an oversized/unparseable DHCP OFFER

The bulb receives the OFFER and discards it. The most likely reason is the **contents** of the
offer. your IoT VLAN's DHCP config carries a non-default option set:

```
dhcp.iot.dhcp_option='3,YOUR_LAN_IP' '6,YOUR_LAN_IP' 'option:domain-search,lan,example.lan,example.net'
```

`option:domain-search` is **DHCP option 119 (RFC 3397)**, which uses compressed domain-name
encoding and here carries **three** domains. Options 3 and 6 are tiny and universal; **option
119 is the unusual, bulky one.**

Minimal embedded DHCP clients — notably the **lwIP stack used on Realtek Ameba / RTL8710BN** —
are known to have small receive buffers and limited option parsers, and to silently drop offers
they cannot parse. **"Repeated DISCOVER, valid OFFER, never a REQUEST" is the classic signature
of an offer the client received but could not accept.**

This also explains the contrast cleanly: the **AiDot bulb (different silicon/stack) got
YOUR_LAN_IP with no trouble**, as did dozens of ESP-based devices on the same VLAN and SSID.
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
ssh root@YOUR_LAN_IP 'logread -f | grep -i "b0:ce:18"'
```

**Test B (if A fails) — hand the bulb a static lease** so it can skip discovery entirely, and
confirm whether it will talk at all with a known address.

**Test C (diagnostic, no change) — packet-level truth.** Capture on the router to see the exact
offer the bulb rejects:
```sh
ssh root@YOUR_LAN_IP 'tcpdump -i br-lan.8 -n -s0 -vv port 67 or port 68'
```
Read the OFFER's total length and option list. If it is near/over a small buffer bound, that
confirms the hypothesis outright.

**Success criterion for all three: a `DHCPREQUEST` followed by `DHCPACK` in the dnsmasq log.**
Until that appears, nothing else about the bulb's provisioning can be judged.

## 🤝 Handoff — tool-side half
The evidence **moves the problem off the network entirely** — but note it may *not* be
tool-side either, since the bulb fails at plain DHCP, before any Sengled protocol runs.
Two things worth checking on the tool side anyway:
1. The bulb never reaching an IP means the `appServerDomain` / `jbalancerDomain` values handed
   to it are moot **for this failure** — don't chase them until DHCP completes.
2. Once a lease appears, the next thing to verify is whether those URLs (built from
   `get_local_ip()` while the workstation sat on the bulb's 192.168.8.x SoftAP) are still reachable from
   your IoT VLAN — a 192.168.8.x server address would be unreachable at YOUR_LAN_SUBNET.x and would produce a
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
