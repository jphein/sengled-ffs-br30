# OTA (No-Solder) Reflash Path — "FFS / Sengled" BR30 RGBCW WiFi Bulb (ASIN B097CYHRZJ)

**Status:** IN PROGRESS (started 2026-08-09)
**Sourcing:** FCC exhibit records, upstream project docs, community tooling matrices, and observation of a real bulb.
**Question:** Can these 8 bulbs be flashed with open firmware over-the-air, without soldering UART?

## VERDICT — FINAL / CONFIRMED / ADOPTED

> **Settled 2026-08-09.** Hardware identity is no longer inferred — the module was read
> directly off photos: **`WF864SM-M6`, FCC ID `2AGN8-WF864`, IC `20888-WF864`**, board
> `LLPC35560_V1` (2020-12-02) = **MXCHIP MX1290 = Realtek RTL8710BN**. Bulb is Sengled
> **W12-N15**. Genuine-Sengled corroborated twice more: SoftAP name `Sengled_Wi-Fi Bulb_XXXX`
> and MAC OUI **`B0:CE:18`** (Zhejiang Shenghui Lighting = Sengled). Vendor OUI, from the IEEE registry.

**Three-line answer:**

1. **No tuya-cloudcutter, no tuya-convert.** Genuine Sengled firmware, not Tuya — there is no
   Tuya activation handshake to exploit. Both tools are inapplicable by construction, not by
   firmware version. (tuya-convert is additionally dead/archived.)
2. **No solderless OTA flash on WF864.** The only Sengled OTA flasher (`SengledTools`) pushes
   an **ESP8266 (Xtensa) shim**; WF864/MX1290 is an ARM Cortex-M4F. Not flashable OTA.
3. **✅ ADOPTED — Path A: `SengledTools` + its `sengled_udp` Home Assistant integration.**
   Local UDP control on port 9080. **No flashing, no soldering, no vendor app, no Sengled
   account, no cloud.** All 8 bulbs, no hardware work.

**Closed out:** my Round-1 residual doubt ("what if some W12-N15 are ESP8266 / WF863?") is now
**dead** — the FCC ID reads `2AGN8-WF864`. Do not reopen it, and **never pass `--force-flash`**
(see R2 below for why that is the one command that can actually brick these).

**Verified CLI (read from `sengled_tool.py` argparse, not docs):** `--setup-wifi` (interactive),
`--ssid` / `--password` (non-interactive), `--ip` (UDP control), `--mac` (MQTT control),
`--diagnose`. All present as documented.

---

## Original round-1 framing (retained for reasoning trail)

**The premise is wrong in the best possible way.** This is not a Tuya bulb, so neither
tuya-cloudcutter nor tuya-convert applies. But you also **don't need to flash anything, and
you don't need to solder anything** — the goal (8 bulbs, fully local, in Home Assistant) is
reachable with a laptop and a power switch.

1. **OTA-flash to open firmware: ❌ NOT viable on this bulb.** It is a Sengled **W12-N15**
   (Wi-Fi BR30 multicolor). Its radio is the **WF864 module / MXCHIP MX1290**. The only
   solderless flashing tool that exists for Sengled (`SengledTools`) can push its rescue shim
   **only to ESP8266EX / WF863 modules**. WF864 is explicitly excluded.
2. **Local control with NO flashing and NO soldering: ✅ FULLY VIABLE, and proven on exactly
   this model.** `SengledTools` does local Wi-Fi onboarding via the bulb's own AP, stands up a
   local HTTP+MQTT server in place of Sengled's dead cloud, and ships a Home Assistant
   integration. **PR #63 (merged ~Jun 2026) was tested on "W12-N15 bulbs on stock firmware"**
   and fixed exactly the out-of-box-activation / credentials-don't-persist problem.
3. **UART is NOT a sensible fallback here either.** Soldering all 8 gets you to an
   MX1290 (= Realtek RTL8710BN), which LibreTiny/ltchiptool nominally support — but there is
   **zero prior art** for flashing a Sengled WF864 bulb, and MX1290 is reported to ship with
   flash encryption / UART logging disabled. That is speculative R&D on 8 units, for a
   capability you already get for free in (2).
4. **The vendor app being unusable is not your fault and not a blocker.** Sengled's cloud
   collapsed in June 2025 and Amazon killed the Alexa skill on 2025-08-01. The whole reason
   these tools exist is that the app can no longer work for *anyone*.

### The one check that settles it — read the FCC ID printed on the bulb

| FCC ID on bulb | Module | Chip | Solderless flash to Tasmota/ESPHome/WLED? |
|---|---|---|---|
| `2AGN8-WF863` | WF863 | Espressif ESP8266EX | ✅ **Yes** — SengledTools `--upgrade` |
| `2AGN8-WF864` | WF864 | MXCHIP MX1290 (RTL8710BN) | ❌ No — local control only |
| `2AGN8-WF862` | WF862 | MXCHIP MX1290 | ❌ No — local control only |
| (EMW3091) | EMW3091 | MXCHIP | ❌ No — local control only |

Expect **`2AGN8-WF864`**. If it surprises us and reads `2AGN8-WF863`, the full OTA flash to
ESPHome/Tasmota/WLED is on the table for all 8 with no soldering.

### Recommended plan (either way, no soldering)

```bash
git clone https://github.com/HamzaETTH/SengledTools.git && cd SengledTools
pip install -r requirements.txt
python sengled_tool.py --setup-wifi      # repeat per bulb
```
- Factory-reset each bulb: flick the power switch **5+ times** until it flashes.
- Laptop joins the bulb's own AP `Sengled_Wi-Fi Bulb_XXXXXX` (bulb is `192.168.8.1`, UDP
  `9080`); wizard pushes your SSID/PSK (RC4-encrypted `setParamsRequest`), then the bulb
  calls the local server's `/jbalancer/new/bimqtt` + `/life2/device/accessCloud.json` and
  binds to the local MQTT broker.
- Then in HA: install the bundled **`sengled_udp`** custom integration — bulbs appear as
  light entities driven over **UDP 9080**, *"no cloud, no MQTT broker, and no flashing."*
  (Alternative, heavier: `FalconFour/ha-sengled-local` + its add-on + Mosquitto.)

**Hardware needed:** an ordinary laptop with normal Wi-Fi client mode. **No AP-mode adapter,
no monitor mode, no special chipset, no Docker, no Linux requirement.** A **USB Ethernet
adapter is strongly recommended** (a second NIC lets you stay on the LAN while the Wi-Fi is
attached to the bulb's AP — the dev.to write-up calls this critical for iteration).

**Practical friction to expect:** the pairing flow was TLS-fragile (ALPN `x-amzn-mqtt-ca`,
TLS 1.2 cipher narrowness, cert SAN invalidated when the host IP changes). PR #63 fixed all
three — **use current master, and give the host a static LAN IP** so the cert SAN stays valid.

### Answers to the four questions as asked

1. **tuya-cloudcutter** — real, maintained, works by impersonating Tuya's cloud during device
   activation to push firmware with no disassembly. Needs Linux + NetworkManager + Docker +
   sudo and a **secondary Wi-Fi adapter whose driver supports AP mode via `nmcli`** (keep
   internet on Ethernet). Supports **BK7231T/N, RTL8710BN, RTL8720CF** — **not ESP8266/8285**.
   Flashes LibreTiny-ESPHome/OpenBeken images (`bk7231x_app.ota.ug.bin`) via a device
   "profile" that must already exist for your exact device+firmware. **Defeated by any
   firmware built on the post-Feb-2022 patched Tuya SDK.** **Inapplicable here — not Tuya.**
2. **tuya-convert** — effectively **deprecated**. Patched by Tuya years ago, repo unmaintained;
   only converts old unpatched stock. **Inapplicable here — not Tuya.**
3. **Genuine Sengled?** — **Yes, genuine Sengled.** "FFS" is not a brand: it is a fragment of
   Sengled's own SKU `W12-N15WFFS2P`. Sengled ran its own cloud, not Tuya's. This **does kill
   the Tuya OTA exploit path** — but it does **not** force UART, because Sengled's own
   protocol has been reverse-engineered and re-hosted locally.
4. **HA-native path without the app?** — **Yes, and with no Sengled account.** `sengled_udp`
   (in SengledTools) = local UDP, no cloud, no broker, no flashing. `ha-sengled-local` =
   local MQTT server + add-on. Both are post-shutdown designs, so neither can depend on
   Sengled's cloud. ⚠️ **Avoid** the older `jfarmer08/ha-sengledapi` / `ripleyeldridge`
   /`kylev/ha-sengledng` — those proxy the **Sengled cloud API**, which no longer exists.

---

## Working notes

### F1. tuya-cloudcutter does NOT support ESP8266/ESP8285 — chip identity is decisive

Verified from the upstream README and LibreTiny docs:

- Supported chips: **Beken BK7231T, BK7231N** (unpatched), **Realtek RTL8710BN** (unpatched,
  SDK 2.0.0 excluded), **RTL8720CF** (unpatched, caveats).
- **Explicitly NOT supported: ESP8266, ESP8285, or other chipsets.**
- LibreTiny doc is blunter still: *"This currently applies to BK7231T and BK7231N only.
  `tuya-cloudcutter` can't be used for other chips."*

=> If the parallel chip-ID agent finds an **ESP8285**, cloudcutter is off the table by
construction, not by firmware version.

### F2. Cloudcutter is defeated by patched Tuya SDK (Feb 2022+)

- README: *"Tuya has patched their SDK as of February 2022. Any device with firmware compiled
  against a patched SDK will not be exploitable."*
- Known-patched BK7231N firmware versions listed on the wiki include 1.1.2, 1.1.12, 1.1.15,
  1.3.3, 1.3.8, 1.3.10, 1.5.10, 2.0.15.
- A bulb bought in the B097CYHRZJ era (listing live ~2021) *could* predate the patch, but
  only matters if the chip is Beken at all.

### F3. Cloudcutter host/adapter requirements (for completeness)

- Linux host with **NetworkManager + Docker + sudo**. Uses `nmcli` to bring up an AP.
- README asks for "a stand-alone wifi adapter" that is **not** your primary networking path
  (Ethernet preferred for internet). It does **not** publish a chipset allow/deny list in the
  README itself — needs the INSTRUCTIONS.md / wiki for hard adapter guidance. (chasing)

### F4. *** The bulb is very likely GENUINE Sengled, not rebadged Tuya ***

- Amazon `B097CYHRZJ` title: *"**Sengled** Smart Light Bulbs, Updated FFS Smart Bulb That
  Work With Alexa, Google, Smart Recessed Light Bulbs 65W Equivalent, 7.5W, Color Changing
  Light Bulb, 2.4GHz WiFi Only, No Hub Required, 2 Pack"* — brand field **Sengled**.
- "FFS" is not a separate brand; it is a keyword inside Sengled's own Amazon titles. Sibling
  ASIN `B097CZ49V8` = *"Sengled BR30 Smart Light Bulb, Updated FFS WiFi Led Flood Light
  Bulbs..."* (same family, white version). Both are Sengled listings.
- Sengled runs **its own cloud**, not Tuya's. Sengled WiFi bulbs pair with the *Sengled Home*
  app and talk MQTT to Sengled servers — they are **not** Smart Life / Tuya devices.
- Known Sengled WiFi hardware: **W31-N15 RGBW bulb = ESP8266**, and the Tasmota template for
  it lists flashing method **"USB to Serial"** (i.e. wired), with the note *"Programming pins
  hidden behind capacitors, you may need to fully remove module to flash"*. No OTA path.

=> Genuine Sengled => no Tuya firmware => **no tuya-cloudcutter, no tuya-convert.** Those
exploits target Tuya's SDK specifically; they have nothing to attack here.

### F5. *** Sengled's cloud is DEAD (2025) — and that opened a LOCAL path ***

- June 18 2025: Sengled's cloud went down hard; WiFi bulbs stopped responding via app, Alexa
  and Google. Outages recurred through July 2025.
- Aug 1 2025: **Amazon permanently discontinued the Sengled Alexa skill**, citing "repeated
  extended service interruptions."
- Sengled reportedly in financial crisis — staff unpaid since Jan 2025, strikes by Apr 2025.

This is why the vendor app is unusable — it is not a user problem, the backend is gone.

- **`FalconFour/ha-sengled-local`** — HA integration + add-on that stands up a **local
  replacement Sengled server** (MQTT). README: *"brings your Sengled smart bulbs back to life
  after Sengled shut down their cloud servers."* Supports **"All WiFi Sengled Bulbs"**, and
  **only** the "No Hub Required" WiFi models — which is exactly what B097CYHRZJ is.
- Pairing is done by a companion tool, **SengledTools**, which must be pointed at the add-on's
  `/bimqtt` and `accessCloud.json` URLs instead of Sengled's.

=> Candidate answer: **don't reflash at all.** Re-point the stock firmware at a local server.

### F6. *** SengledTools — the actual tool for this bulb *** (`HamzaETTH/SengledTools`)

84 stars, 149 commits, active. Python 3.10+. Three capabilities:

1. **Local Wi-Fi pairing** — no app, no cloud, no account. The bulb itself broadcasts an AP
   `Sengled_Wi-Fi Bulb_XXXXXX`; your laptop joins it as an ordinary client and provisions
   credentials over UDP+HTTP. **No AP-mode adapter, no monitor mode, no special chipset,
   no Docker.** Factory reset = flick power 5+ times until it flashes.
   - `python sengled_tool.py --setup-wifi`
2. **Local control, no flashing** — HA custom integration `sengled_udp` drives the bulbs over
   **UDP port 9080** on the LAN. README: *"no cloud, no MQTT broker, and no flashing."*
   Also can pair bulbs to your own MQTT broker.
   - Critically: *"Basic MQTT/UDP control works on **most, if not all**, Sengled Wi-Fi bulbs,
     **even when flashing is not supported**."*
3. **OTA flashing to open firmware — ESP8266 models ONLY.** Pushes a `Sengled-Rescue` shim
   over the air (`--upgrade firmware/shim.bin`), which exposes a rescue-bootloader web UI
   that can back up the chip and then flash **Tasmota / ESPHome / WLED**. Fully solderless.

**SengledTools flashability matrix (verbatim from README):**

| Model | Module | Chip | Flashable? |
|---|---|---|---|
| W31-N15 | WF863 | Espressif ESP8266EX | ✅ yes |
| W31-N11 | WF863 | Espressif ESP8266EX | ✅ yes |
| W21-U23 | — | Espressif ESP8266EX | ✅ yes |
| **W12-N15** | **WF864** | **MXCHIP MX1290** | ❌ **no** |
| W21-N13 | — | MXCHIP EMW3091 | ❌ no |
| W11-N13 | — | MXCHIP EMW3091 | ❌ no |

> *"Flashing only works with ESP8266EX-based modules (WF863). Other modules like WF864
> (MX1290 chip) or EMW3091 are not flashable via this method."*
> *"Check your bulb's FCC ID — Look on the side of your bulb for the FCC ID. It identifies
> the module/chip inside and tells you if flashing is supported."*

Brick warning: *"Flashing firmware carries risk of permanently bricking your bulb."* Known
gotcha: some bulbs boot `ota_0` instead of `ota_1`, which blocks flashing — the Rescue UI has
a **"Relocate to ota_1"** fix. Rescue UI also offers a **full chip backup** before flashing.

### F7. *** THE BULB IS ALMOST CERTAINLY W12-N15 — the NON-flashable row ***

Best Buy SKU 6463039: *"Sengled Smart BR30 LED Bulbs Wi Fi Works with Amazon Alexa & Google
Assistant (2 Pack) Multicolor **W12-N15WFFS2P**"*.

Decode: `W12-N15` + `WF` (Wi-Fi) + **`FS`** + `2P` (2-pack). That **`WFFS`** is the source of
the "**Updated FFS**" wording in the Amazon title — "FFS" is Sengled's own SKU fragment, not a
third-party brand. B097CYHRZJ is the BR30 multicolor 2-pack; B097CYZWQ1 the 4-pack;
B097CZ49V8 the daylight sibling. All the same `W12-N15…WFFS…` family.

(Note: SengledTools' README labels W12-N15 "WiFi white LED" while Best Buy sells it as
Multicolor — a description slip in the README. The **model number and module are what matter**
and they match.)

### F8. What MX1290 actually is — and why UART is not a clean fallback either

- MXCHIP **MX1290 = Realtek RTL8710BN** (ARM Cortex-M4F @125MHz, 256KB SRAM, 2MB flash).
  Sengled's module family is **WF862 / WF863 / WF864**, FCC IDs of the form **`2AGN8-WF86x`**
  (the MX1290 module manual on file shows **FCC ID 2AGN8-WF862**, IC 20888-WF862).
- RTL8710BN **is** supported by **LibreTiny** (`realtek-ambz` family) and flashable with
  **ltchiptool** — so ESPHome-over-LibreTiny is theoretically reachable **via UART**.
- Two real caveats: MX1290 is reported to ship *"potentially with **flash encryption and log
  UART turned off**"*, and there is **no published teardown of anyone flashing a Sengled
  W12-N15 / WF864 bulb** — zero prior art. You would be first.
- One comfort: on RTL8710BN the UART loader lives in **ROM**, so per LibreTiny it *"can't be
  software-bricked, even if you damage the bootloader."*

### F9. tuya-convert — dead, and irrelevant here anyway

- Exploits pre-2020/2021 Tuya firmware; Tuya patched it, `ct-Open-Source/tuya-convert` is
  archived/unmaintained. Only works on old-stock unpatched **Tuya** devices.
- Moot regardless: this is not a Tuya device.

### F10. Why tuya-cloudcutter cannot be used here (two independent reasons)

1. **Wrong vendor.** Cloudcutter attacks the **Tuya SDK's** cloud-activation flow. Sengled
   firmware is Sengled's own (its own cloud, its own MQTT, its own app). There is no Tuya
   activation handshake to exploit. Even where the *chip* is in scope, the *firmware* is not.
2. **Would be moot anyway.** Even RTL8710BN — which cloudcutter nominally lists — is only
   exploitable when running unpatched **Tuya** firmware, and Tuya patched the SDK Feb 2022.

For the record, cloudcutter's host requirements (in case a genuinely Tuya device shows up
later): Linux + NetworkManager + Docker + sudo; a **dedicated/secondary Wi-Fi adapter** that
is not your primary uplink (use Ethernet for internet) and that supports **AP mode via
NetworkManager/`nmcli`**. The project publishes **no chipset allow/deny list**; in practice
the requirement is simply "an adapter whose driver supports AP mode" — mac80211-native
drivers (ath9k/ath9k_htc, mt76, rt2800usb, brcmfmac) are the safe class; out-of-tree Realtek
`rtl8812au`/`8821au` DKMS drivers are the flaky class. Not needed for this project.

---

## Confidence & what I verified vs inferred

**Verified (read from source):**
- cloudcutter's supported-chip list and the "ESP8266/ESP8285 not supported" exclusion; the
  Feb-2022 patched-SDK statement; the Linux+NetworkManager+Docker host requirement.
- LibreTiny's "BK7231T and BK7231N only" statement for cloudcutter; its supported-family list;
  its CPU list entry **"MX1290 (RTL8710BN)"**; the ROM-UART-loader / can't-software-brick note.
- SengledTools' flashable/non-flashable model table, the FCC-ID identification advice, the
  brick warning, the `ota_0`->`ota_1` relocation fix, the `--setup-wifi` / `--upgrade`
  commands, the UDP-9080 integration, and *"Basic MQTT/UDP control works on most, if not all,
  Sengled Wi-Fi bulbs, even when flashing is not supported."*
- **PR #63 tested on "W12-N15 bulbs on stock firmware"** — the decisive datum.
- FCC IDs `2AGN8-WF864` / IC 20888-WF864 (MX1290, ARM M4F) and `2AGN8-WF862`, from Sengled's
  own module manuals.
- Best Buy SKU `W12-N15WFFS2P` = "Sengled Smart BR30 LED Bulbs Wi Fi ... (2 Pack) Multicolor".
- Sengled cloud outage June 2025; Alexa skill discontinued 2025-08-01; unpaid staff/strikes.
- Sengled W31-N15 Tasmota template lists flashing method **"USB to Serial"** with programming
  pins hidden behind capacitors — i.e. even the ESP8266 model has no *vendor* OTA path; the
  OTA path is SengledTools' own shim.

**Inferred (flag if it matters):**
- **B097CYHRZJ => W12-N15.** Chain: Amazon title says "Updated **FFS**" + BR30 + multicolor +
  2-pack; Best Buy sells the BR30 Wi-Fi multicolor 2-pack as `W12-N15`**`WFFS`**`2P`.
  Independently corroborated by Sengled's form-factor digit convention (`E12-N14` = Zigbee
  **BR30** Element Classic, `B12-N1E` = Bluetooth **flood**) => `W12` = **Wi-Fi BR30**.
  Strong, not certain.
- SengledTools' README labels W12-N15 "WiFi white LED" while Best Buy sells W12-N15 as
  Multicolor. I treat this as a description slip in the README; **model number + module are
  what the table keys on.** Hardware revisions within one model number are also possible —
  which is exactly why the **FCC ID on the bulb is the authoritative check.**
- One low-quality contradiction: the dev.to write-up appears to call its bulbs "W12-N15 ...
  ESP8266-based". That same article also writes "W15-N15" and "W31-115", so its model strings
  are unreliable typos; its ESP8266 remarks most plausibly attach to the W31 series. **If the
  FCC ID comes back `2AGN8-WF863`, this footnote becomes the headline** and full solderless
  OTA flashing to Tasmota/ESPHome/WLED is available for all 8.
- The teardown clue "**UART** silkscreened on the module" is consistent with WF864 — Sengled's
  MX1290 module manual documents UART/I2C/SPI/PWM pin interfaces. It does not by itself
  distinguish WF863 from WF864.

**No prior art found** for flashing a Sengled WF864 / MX1290 bulb by any means, UART included.

## Sources

- https://github.com/tuya-cloudcutter/tuya-cloudcutter
- https://github.com/tuya-cloudcutter/tuya-cloudcutter/wiki/Known-Patched-Firmware
- https://docs.libretiny.eu/docs/flashing/tools/cloudcutter/
- https://docs.libretiny.eu/docs/status/supported/
- https://docs.libretiny.eu/docs/platform/realtek-ambz/
- https://github.com/libretiny-eu/ltchiptool
- https://github.com/ct-Open-Source/tuya-convert (archived) · https://tasmota.github.io/docs/Tuya-Convert/
- https://github.com/HamzaETTH/SengledTools · README · `/pull/63` · `/issues/62`
- https://github.com/FalconFour/ha-sengled-local · https://github.com/FalconFour/HA-Sengled-Local-Server-AddOn
- https://templates.blakadder.com/sengled_W31-N15.html
- https://manuals.plus/sengled/wf864-sengled-wifi-module-manual · https://manuals.plus/sengled/mx1290-wi-fi-module-manual
- https://www.bestbuy.com/site/6463039.p (SKU `W12-N15WFFS2P`)
- https://www.amazon.com/dp/B097CYHRZJ · https://www.amazon.com/dp/B097CYZWQ1
- https://inside.lighting/news/25-06/smart-lighting-cloud-failure-leaves-users-dark
- https://www.lightnowblog.com/2025/08/sengled-smart-lamps-service-outages-alexa-skill-shut-down/
- https://dev.to/toolboc/teaching-an-ai-agent-to-talk-to-a-light-bulb-and-why-i-had-to-get-up-from-my-desk-2i00

---

# ROUND 2 — SoftAP scan confirmed, source code read directly

Owner's live scan: the powered bulb broadcasts an **open** AP named
**`Sengled_Wi-Fi Bulb_XXXX`**. That is a **verbatim match** for the AP name SengledTools
documents (`Sengled_Wi‑Fi Bulb_XXXXXX`) and is nothing like a Tuya SoftAP
(`SmartLife-XXXX` / `A19-XXXX`). **Genuine Sengled firmware — confirmed independently.**

I stopped reading docs and **cloned the repo to read the source** (a scratch clone).
Everything below is read off the actual code, not documentation.

### R1. Answering (1): is there ANY no-solder OTA route for genuine Sengled? — **Yes, but only for ESP8266 models**

There is exactly one, and it is real: SengledTools pushes `firmware/shim.bin` through
**Sengled's own stock OTA path**, landing a "Sengled-Rescue" bootloader with a web UI that
can back up the chip and flash Tasmota / ESPHome / WLED. No soldering anywhere.

**But the shim is ESP8266 machine code.** Verified by strings in the binary:
```
/Users/falcon/Downloads/esp_rtos/ESP8266_RTOS_SDK/components/app_update/esp_ota_ops.c
/Users/falcon/Downloads/esp_rtos/ESP8266_RTOS_SDK/components/esp8266/source/startup.c
Sengled-Rescue ready to roll!
Not ESP8266 image slated for boot, avoiding brick
```
(Build path `/Users/falcon/…` — same author as `FalconFour/ha-sengled-local`; the two
projects are one effort.)

So the **OTA transport is chip-agnostic** — it's Sengled's own updater — and the blocker is
purely that **no shim has been built for MX1290/RTL8710BN**. That's a missing artifact, not a
locked door. Worth an upstream feature request; not something to wait for.

### R2. *** The flashing gate is an ALLOWLIST, not a chip test — and `--force-flash` exists ***

`sengled/constants.py`, verbatim:
```python
SUPPORTED_TYPECODES = {
	"W31-N11",
	"W31-N15",
}
COMPATIBLE_IDENTIFY_MARKERS = (
	"ESP8266",
)
```
`sengled/wifi_setup.py` classifies into `supported` / `untested` / `not_supported`, and
`sengled_tool.py` hard-gates:
> `"This model/module is not supported for flashing. Re-run with --force-flash to override."`

**⚠️ SAFETY — do NOT use `--force-flash` on a non-ESP8266 module.** The gate is the only thing
standing between you and pushing an Xtensa ESP8266 binary onto an ARM Cortex-M4F. The shim's
internal `"Not ESP8266 image slated for boot, avoiding brick"` guard **cannot save you** — that
check runs *inside the shim*, which only ever executes on an ESP8266. Whether the stock MX1290
bootloader rejects the malformed image (safe) or accepts it (brick, recoverable only by
soldering) is **unverified**. On 8 bulbs, do not find out.

### R3. *** Identify the chip OVER THE AIR in ~10 seconds — no teardown, no FCC ID, no pairing ***

The bulb reports its own identity over **plain, unauthenticated JSON-over-UDP on port 9080** —
verified in `sengled/udp.py`:
```python
s.sendto(encoded_payload, (bulb_ip, BULB_PORT))   # BULB_PORT = 9080
```
`sengled/diagnose.py` queries `get_device_mac`, `get_software_version`, `get_device_mode`,
`search_devices`, then extracts the model with `re.search(r"_(W\d{2}-[A-Z]\d{2})_", version)` —
i.e. the **version string embeds the model**, e.g. `..._W12-N15_SYSTEM_...`. `search_devices`
additionally returns `R`/`G`/`B` keys on colour-capable bulbs.
(`config_flow.py` uses the same probe, preferring an explicit `MN` field, with the code's own
worked example being `_W21-N13_SYSTEM_`.)

**Deliverable: `research/probe_bulb.py`** (written, syntax-checked, smoke-tested).
- Bulb in SoftAP mode → join the open `Sengled_Wi-Fi Bulb_XXXX`, run `./probe_bulb.py`
  (defaults to `192.168.8.1`).
- Bulb already on the LAN → `./probe_bulb.py <bulb-ip>`.
- Prints model, RGB-vs-white, and a flash verdict.

Caveat, stated honestly: the *paired-bulb* path is exactly what `--diagnose` does, so it is
solid. Whether the bulb answers these same funcs **while still in SoftAP mode** is a
**reasonable inference, not verified** — SengledTools' own pairing talks UDP to
`192.168.8.1:9080`, so the listener is up on that socket; whether `get_software_version` is
serviced pre-pairing is untested. It costs one command to find out, and failing tells you
nothing bad.

### R4. Answering (2): local control with no vendor app and no Sengled account — **yes, unambiguously**

Confirmed in source, not just README:
- `custom_components/sengled_udp/` — a real HA integration (`light.py`, `config_flow.py`) that
  discovers and drives bulbs over UDP/9080. **No cloud, no broker, no flashing, no account.**
- `sengled/mqtt_broker.py` + `sengled/http_server.py` — the tool **embeds its own MQTT broker
  and HTTP server**, standing in for Sengled's dead cloud during pairing (`--run-servers`).
- Identity/attributes arrive on `wifielement/<MAC>/status`; pairing params are RC4-encrypted
  (`sengled/crypto.py`) against the bulb at `192.168.8.1:9080`.

A Sengled account is **structurally impossible to require** — the backend it would authenticate
against no longer exists. These tools are post-mortem replacements for it.

### R5. Plainly: is it "UART only"? — **NO.**

**It is not UART-only, and UART is the worst of the three options.**

| Goal | Route | Solder? | Viable on this bulb |
|---|---|---|---|
| Local control in HA | SengledTools + `sengled_udp` | **No** | ✅ **Yes — do this** |
| Open firmware (Tasmota/ESPHome/WLED) | SengledTools shim OTA | No | ❌ ESP8266 models only |
| Open firmware | UART + ltchiptool (`realtek-ambz`) | **Yes ×8** | ⚠️ Unproven, no prior art |

If — and only if — the probe reports `W31-N15`/`W31-N11`, option 2 opens up for all 8 with no
soldering. Otherwise take option 1 and stop: it delivers the actual objective (8 bulbs, local,
in Home Assistant, no cloud, no app) without touching a soldering iron.

### R6. Corrected detail from Round 1

Reading the README in full, its own prose is **hedged** where my earlier summary was flat:
> *"**Other bulbs appear to use other modules** (like WF864, based on MX1290 chip), which
> **may** not work with the flashing process."*

So "W12-N15 = not flashable" is the maintainer's **conservative default**, driven by the
2-entry allowlist, not by a confirmed teardown of a W12-N15. The `identifyNO` module string the
bulb reports during pairing is the real evidence — if it contains `ESP8266`, the tool itself
reclassifies the bulb as `untested` and **permits** flashing. This slightly *raises* the odds
for the owner's bulbs versus my Round 1 verdict, and it is settled for free by R3's probe.

---

# ROUND 3 — sync, close-out

**CONFIRMED** via module photos: `WF864SM-M6` / FCC ID `2AGN8-WF864` / MX1290 /
RTL8710BN. Path A adopted. Reconciling this file against the project notes:

- **Round-1 inference chain validated end to end.** `B097CYHRZJ` → "FFS" = SKU fragment of
  `W12-N15WFFS2P` → `W12` = Wi-Fi BR30 → WF864/MX1290. The FCC ID I nominated as the decisive
  test (`2AGN8-WF864` vs `2AGN8-WF863`) was the one actually read, and it returned WF864.
- **The one open question is now closed.** The dev.to "W12-N15 … ESP8266-based" claim is
  refuted by the physical FCC ID; as suspected, that article's model strings were typos.
  No solderless flash path exists for these 8 bulbs.
- **`probe_bulb.py` is now redundant for chip ID** but remains useful as a **liveness/identity
  check** during pairing — it reads model, MAC and RGB-capability over UDP/9080 without
  touching Home Assistant. Consistent with the observed "all TCP ports closed, UDP only".
- **Verified for the in-flight pairing:** `--setup-wifi`, `--ssid`, `--password`, `--ip`,
  `--mac`, `--diagnose` all exist in `sengled_tool.py`'s argparse. The documented command line is
  correct.
### Carry-forward warnings — both are now in the main writeup

1. **`--force-flash` must be documented as DO-NOT-USE for WF864**, not merely "advanced".
   The gate is a 2-entry allowlist (`{"W31-N11","W31-N15"}`), and overriding it pushes an
   Xtensa binary at an ARM core. The shim's own `"Not ESP8266 image slated for boot, avoiding
   brick"` guard executes *inside the shim* and therefore only ever protects an ESP8266.
2. **The OTA transport is chip-agnostic** — it's Sengled's own updater. The only missing piece
   for OTA-flashing WF864 is an **MX1290/RTL8710BN shim binary**. That is a legitimate upstream
   feature request (`HamzaETTH/SengledTools`), and worth noting in the repo as the thing that
   would unlock solderless open firmware for this whole bulb family. Not something to wait on.
3. Only the generic `Sengled_Wi-Fi Bulb_XXXX` AP name is safe to publish — no real network SSIDs,
   no LAN addresses, no device MACs. (The `B0:CE:18` OUI above is a public IEEE vendor
   registration, not a device address.)

**Status: COMPLETE — verdict final, adopted, wrapped.** 2026-08-09
