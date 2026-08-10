# Chip ID Research — "FFS / Sengled" BR30 RGBCW WiFi Bulb (ASIN B097CYHRZJ)

**Status:** COMPLETE (2026-08-09 21:15 PDT)
**Sourcing:** FCC exhibit records, upstream project docs, community tooling matrices, and observation of a real bulb.

---

## ⚡ BOTTOM LINE UP FRONT

**It is NOT Beken, NOT Realtek, NOT Tuya.** This is a first-party **Sengled** bulb running
Sengled's own firmware on a Sengled-designed **WF86x** module. Confidence **95%**.

The real question is *which* Sengled module, and it is a genuine two-way fork:

| | **WF863** | **WF864 / EMW3091** |
|---|---|---|
| Chip | **Espressif ESP8266EX** | **MXCHIP MX1290** (Cortex-M4F) |
| Flashable? | ✅ **YES — over the air, no soldering** | ❌ Not via the community tool |
| My odds | **~45%** | **~45%** (~10% other WF86x) |

**Do not solder anything yet.** If it's a WF863, the community tool flashes it **over Wi-Fi**
— the teardown was unnecessary. See §6.

**The one marking to read:** flip the module over. The **bottom silkscreen literally prints
`M/N: WF86x` and `FCC ID: 2AGN8-WF86x`.** That single line ends the question. (Reference
photos saved in `research/img/`.)

## Target

- Amazon ASIN **B097CYHRZJ** — "Updated FFS Smart Bulb That Work With Alexa, Google, Smart
  Recessed Light Bulbs 65W Equivalent, 7.5W, Color Changing Light Bulb, 2.4GHz WiFi Only,
  No Hub Required, 2 Pack"
- Brand field shows **Sengled** (suspicious — see below)
- Form factor: BR30 recessed/flood, E26, RGBCW, 7.5W (65W equiv), 2.4GHz WiFi only, no hub
- Owner teardown clue: WiFi module has **"UART" silkscreened** on it

## Working notes

### Finding 1 — "FFS" is NOT a brand. It's Amazon Frustration-Free Setup.
The listing title reads "Updated FFS Smart Bulb". FFS = **Amazon Frustration-Free Setup**
(Wi-Fi Simple Setup / zero-touch provisioning against an Echo already on the network).
So there is no "FFS" manufacturer to chase — **the brand really is Sengled**.

### Finding 2 — This is genuine Sengled, NOT a Tuya rebadge. (high confidence)
- Sengled Co., Ltd. holds its own FCC grantee code **2AGN8** (54 grants, 2016–2025),
  including a whole family of self-designed Wi-Fi modules.
- Sengled ships its own cloud + "Sengled Home" app, its own OTA, own MQTT/UDP protocol.
- Consequence: **`tuya-convert` does NOT apply** — there is no Tuya OTA endpoint to hijack.
  ✅ **Corrected by Finding 4:** this does *not* mean serial-only. Sengled's **own** OTA
  mechanism is exploitable — `SengledTools` impersonates the Sengled cloud with a local MQTT
  broker + HTTP server and pushes an arbitrary image. So on ESP8266 units, flashing is still
  **wireless**; it just uses a Sengled-specific path instead of a Tuya one.

### Finding 3 — Sengled's own Wi-Fi module family (FCC 2AGN8), with silicon
| Module | FCC ID | Granted | Chip |
|---|---|---|---|
| WF861 | 2AGN8-WF861 | 2020-11-02 | (not yet confirmed) |
| WF862 | 2AGN8-WF862 | 2021-04-05 | (not yet confirmed) |
| **WF863** | 2AGN8-WF863 | 2021-04-20 | **Espressif ESP8266EX** ✅ flashable |
| **WF864** | 2AGN8-WF864 | 2021-06-11 | **MXCHIP MX1290** (ARM Cortex-M4F, 133MHz, 256KB SRAM, 512KB ROM) ❌ not flashable |
| WF866 | 2AGN8-WF866 | 2022-11-14 | (not yet confirmed) |
| WF867 | 2AGN8-WF867 | 2022-03-02 | (not yet confirmed) |
| SLMB01 | 2AGN8-SLMB01 | 2024-06-12 | (not yet confirmed) |

Also seen in the wild: **MXCHIP EMW3091** module (chip unconfirmed) in some RGBW models.

**No Beken BK7231, no Realtek RTL8710/8720, no Tuya WB3S/CB3S/TYWE3S anywhere in the
Sengled line.** The usual "cheap 2023+ RGBCW bulb = BK7231N" heuristic does **not** apply
here, because this is a first-party brand with in-house modules.

### Finding 4 — The community tool: HamzaETTH/SengledTools
https://github.com/HamzaETTH/SengledTools — Sengled-specific. Three paths:
1. Home Assistant local **UDP** custom integration (no cloud, **no flashing needed**)
2. `sengled_tool.py` CLI — UDP/MQTT commands, re-pair bulb to a local MQTT broker
3. Firmware flashing via a shim bootloader called **Sengled-Rescue** (Tasmota/ESPHome/WLED)

Its own compatibility matrix:
- **Flashable:** W31-N15 (RGBW), W31-N11 (white) — WF863 / ESP8266EX; W21-U23 (RGBW) — ESP8266EX
- **NOT flashable:** W12-N15 (white) — WF864 / MX1290; W21-N13 & W11-N13 (RGBW) — MXCHIP EMW3091

> "flashing only works with ESP8266EX-based modules (WF863)"

### Finding 5 — Existing Tasmota template (for the ESP8266 sibling)
`templates.blakadder.com/sengled_W31-N15.html` — Sengled RGBW W31-N15:
```json
{"NAME":"Sengled RGBW","GPIO":[0,0,0,0,0,0,0,0,417,416,419,418,0,0],"FLAG":0,"BASE":18}
```
Notes from the template: requires USB-to-serial; **"Programming pins hidden behind
capacitors, you may need to fully remove module to flash"**; ground IO0 to enter
bootloader.



### Finding 6 — Module hardware, read off FCC internal/external photos (PRIMARY EVIDENCE)

I downloaded and rendered the actual FCC exhibit PDFs rather than trusting summaries.
Saved to `research/img/`.

**WF863 — Espressif ESP8266EX** (FCC 2AGN8-WF863, granted 2021-04-20)
- Green PCB, **metal shield can** over the SoC
- **WHITE CERAMIC CHIP ANTENNA** — a discrete white block soldered at one end, overhanging
  the PCB edge. Unmistakable.
- A **protruding tab/flag off the side carrying 5 gold castellated pads** — a dedicated
  serial/programming header. Silkscreen beside it reads `GND` `3V3` `RX` `TX` (+IO0).
- Bottom silkscreen: `3V3 IO0 IO2 ADC IO16 TX RX GND`, `LLPCB5446_V1 94V-0`, `20200915`,
  `E354554`
- Label text: *"This device contains FCC ID: 2AGN8-WF863"*
- Shield removed (internal photo): large square **QFN** (ESP8266EX) + 8-pin SOIC flash

**WF864 — MXCHIP MX1290** (FCC 2AGN8-WF864, granted 2021-06-11)
- Green PCB, metal shield can with a **QR-code sticker** on top
- **ETCHED PCB-TRACE ANTENNA** — a plain green etched flag, part of the board itself.
  **No white component.**
- Castellated pads along the module's own bottom edge (no protruding tab)
- Bottom silkscreen: `M/N: WF864`, `FCC ID: 2AGN8-WF864`, `IC: 20888-WF864`,
  `E354554 94V-0`, `LLPC05560_V1 20201202`
- Pin labels: `ADC IO16 IO5 GND 3V3 Tx Rx BOOT TOUT`
- Shield removed: two SOIC ICs, one **visibly marked `MXCHIP`**

**WF862** (2021-04-05): small PCB, white ceramic antenna at the bottom, silkscreen prints
`P/N WF862` + `FCC ID:2AGN8-WF862`.
**WF867** (2022-03-02): different form factor — ~18×10mm rectangle, dual-row castellated
pads on both long edges, `V1_20211103 LLPCB6135`.

> ### 🔑 THE FASTEST VISUAL TELL (no magnifier needed)
> **White ceramic antenna block → WF863 → ESP8266 → FLASHABLE.**
> **Plain green etched trace antenna → WF864 → MX1290 → dead end.**

### Finding 7 — About the "UART" silkscreen
Honest answer: **the literal word "UART" does not appear** on the WF863, WF864, WF862 or
WF867 FCC photos I examined — those modules label pins individually (`TX`/`RX`/`GND`/`3V3`).
So the "UART" marking is *not by itself* a module fingerprint. Three possibilities:

1. It's the **bulb's driver PCB**, not the module — a silkscreened `UART` header next to
   where the module's serial pads land. Common on Sengled driver boards.
2. It's a **later production revision** of a WF86x module than the 2020/2021 FCC samples.
3. It's the WF863's **dedicated 5-pad programming tab** (the strongest structural match —
   it is the only Sengled module with serial broken out onto its own protruding flag, which
   is exactly the kind of thing a vendor group-labels `UART`). This nudges me slightly
   toward WF863/ESP8266, but not enough to call it.

Note MX1290 *is* UART-programmable in principle (ISP mode via **UART2, pins PA_29/PA_30**) —
so a "UART" label does not imply ESP either way.

### Finding 8 — Sengled cloud status (verified, and the community README overstates it)
The SengledTools README asserts *"Sengled's original cloud backend is no longer operational."*
What I could actually verify from news sources:
- **18–22 June 2025**: multi-day total cloud outage, Wi-Fi bulbs dead across app/Alexa/Google,
  no public statement from Sengled.
- **31 July 2025**: outage recurred; app would not connect. Speculation about patent
  litigation against Sengled.
- Sengled's **Zigbee and Matter** bulbs were unaffected (local hub control).

I could **not** independently confirm a permanent shutdown as of today (2026-08-09) — treat
"cloud is dead" as *probable but unverified*. Either way the conclusion is the same: this
bulb's cloud is unreliable and worth escaping. ⚠️ Also note the flashing procedure itself
does **not** need Sengled's cloud — the tool stands up a local MQTT broker and HTTP server.

---

## 1. Best determination

**Sengled first-party bulb, Sengled WF86x-family Wi-Fi module — 95% confidence.**
Ruled out with high confidence: Beken BK7231T/BK7231N, Realtek RTL8710BN/RTL8720,
Tuya WB3S/WB2S/CB3S/TYWE3S, and the entire Tuya platform.

Why the "cheap RGBCW bulb in 2023-2026 is probably BK7231N" heuristic **fails here**: that
rule describes white-label ODM bulbs built on Tuya's turnkey platform. Sengled is a real
manufacturer (Sengled Co., Ltd. / Zhejiang Shenghui Lighting) with its own FCC grantee code
**2AGN8** (54 grants 2016–2025), its own module designs, its own app, cloud, MQTT protocol
and OTA. Nothing in its Wi-Fi line has ever been Beken or Realtek.

**Silicon — an honest split, not a single answer:**
- **Espressif ESP8266EX (module WF863) — ~45%**
- **MXCHIP MX1290 (module WF864, or module EMW3091) — ~45%**
- Other WF86x (WF861/862/866/867/SLMB01) — ~10%

Arguments for **MX1290**: WF864 was granted **2021-06-11**, essentially the launch window of
this ASIN family (B097CY…/B097CZ…/B097D1…, mid-2021). "Updated **FFS**" means Amazon
Frustration-Free Setup / Wi-Fi Simple Setup, whose provisioning stack (TLS + Amazon device
cert) is a much more comfortable fit for a Cortex-M4F with 256KB SRAM / 2MB flash than for an
ESP8266. And the known-non-flashable RGBW models (W21-N13, W11-N13) are exactly the
MXCHIP EMW3091 ones.

Arguments for **ESP8266EX**: WF863 granted 2021-04-20, also in window; Sengled shipped both
generations concurrently; and WF863 is the only module with a dedicated broken-out serial tab
matching the owner's "UART" observation.

## 2. Fallback candidates (ranked)

1. **MXCHIP MX1290** in module **WF864** — Cortex-M4F @133MHz, 256KB SRAM, 2MB flash.
   Not flashable via Sengled-Rescue. UART2 ISP (PA_29/PA_30) exists but there is no
   open-firmware target (no Tasmota/ESPHome/LibreTiny port for MX1290).
2. **MXCHIP EMW3091** (also MX1290 silicon, FCC **P53-EMW3091**, MXCHIP's own grant,
   2019-04-17). Same dead end.
3. **Espressif ESP8285** — plausible if a cost-reduced variant appeared; would still be
   Tasmota/ESPHome-friendly. Treat as a bonus outcome.
4. **WF867 / WF866 / SLMB01** — later modules, silicon unconfirmed by me. Would need their
   own investigation; WF867 has a visibly different footprint (dual-row pads).

## 3. ⭐ THE SINGLE MARKING TO READ

> **Flip the Wi-Fi module over and read the bottom silkscreen.** Sengled prints it in plain
> text on the solder side:
>
> ```
> M/N: WF864
> FCC ID: 2AGN8-WF864
> ```
>
> **Report the `WF___` number.** `WF863` = ESP8266 = flashable. `WF864` = MX1290 = not.

Two zero-effort backups if the silkscreen is obscured:
- **The antenna** (works from a photo, no flipping): white ceramic block = **WF863/ESP8266**;
  plain green etched trace = **WF864/MX1290**. Compare against `research/img/`.
- **The bulb's own plastic body** prints `Contains FCC ID: 2AGN8-WF86x` — readable **without
  tearing down the second bulb**. The SengledTools README specifically recommends this:
  *"Check your bulb's FCC ID — it identifies the module/chip inside and tells you if flashing
  is supported."*
- Also useful: the **model number** (`W__-N__`) on the bulb label. Known map below.

Known model → module map (from SengledTools):
| Model | Type | Module / chip | Flashable |
|---|---|---|---|
| W31-N15 | RGBW | WF863 / **ESP8266EX** | ✅ |
| W31-N11 | white | WF863 | ✅ |
| W31-N13H | RGBW (1500lm A21) | ESP8266 | ✅ (issues #42, #47) |
| W21-U23 | RGBW | ESP8266EX | ✅ |
| W1E-NC1 | white | ESP8266 (FCC 2AGN8-W1ENC1) | ✅ (issue #48) |
| W12-N15 | white | WF864 / **MX1290** | ❌ |
| W21-N13 | RGBW | EMW3091 / MX1290 | ❌ |
| W11-N13 | RGBW | EMW3091 / MX1290 | ❌ |

⚠️ I could **not** pin ASIN B097CYHRZJ to a specific `W__-N__` model from public listings —
Amazon does not expose it and Sengled's site is geo/bot-blocked. The owner's label settles it.

## 4. Tooling — use this, it's Sengled-specific

**https://github.com/HamzaETTH/SengledTools** — actively maintained, and the only serious
prior art for these bulbs. Three tracks:
1. **Home Assistant local UDP integration** — bulbs as `light` entities, **no cloud, no
   flashing, no teardown.** Genuinely the right answer for most people.
2. `sengled_tool.py` — CLI over UDP/MQTT; can re-pair the bulb to your own MQTT broker.
3. **Flashing** via the `Sengled-Rescue` shim (`firmware/shim.bin`).

## 5. Templates found (⚠️ none is for a BR30 color — adapt)

Tasmota, **W31-N15 RGBW** (blakadder, the canonical one):
```json
{"NAME":"Sengled RGBW","GPIO":[0,0,0,0,0,0,0,0,417,416,419,418,0,0],"FLAG":0,"BASE":18}
```
Tasmota, **W31-N13H RGBW** — same module, channels reordered (issue #42):
```json
{"NAME":"Sengled RGBW","GPIO":[0,0,0,0,0,0,0,0,416,418,419,417,0,0],"FLAG":0,"BASE":18}
```
Tasmota, **W31-N11** (single-channel white):
```json
{"NAME":"Sengled W31-N11","GPIO":[0,0,0,0,416,0,0,0,0,0,0,0,0,0],"FLAG":0,"BASE":18}
```
Tasmota, **W1E-NC1** (single-channel white, issue #48):
```json
{"NAME":"Sengled W1E-NC1","GPIO":[0,0,0,0,416,0,0,0,0,0,0,0,0,0],"FLAG":0,"BASE":18}
```
**WLED** (LED output mode `PWM RGBW`) — GPIO order:
- W31-N15 → `13, 12, 15, 14`
- W31-N13H → `12, 15, 13, 4`

For an RGBCW BR30 the two white channels may need a 5th PWM; start from the W31-N15 RGBW
template and permute the four `41x` GPIO entries until the channels map correctly.
Blakadder has **no** template for a Sengled BR30 color bulb — publishing one would be new.

## 6. 🔧 Recommended path (in order — DO NOT SOLDER FIRST)

0. **Read the module silkscreen / bulb FCC ID.** Stop and branch on the answer.
1. If you just want it working: **HA local-UDP integration.** No flashing, no risk,
   keeps both bulbs intact.
2. **If WF863/ESP8266 → flash entirely over the air. No UART, no soldering:**
   - Factory reset (flick power 5+ times), join `Sengled_Wi-Fi Bulb_XXXXXX`
   - `python sengled_tool.py --setup-wifi` (stands up local MQTT + HTTP)
   - `python sengled_tool.py --mac <MAC> --upgrade "firmware/shim.bin"`
   - Join the **`Sengled-Rescue`** AP → `http://192.168.4.1` (slow; keep refreshing)
   - **Back up the full flash first** (full → backup selected)
   - boot → choose Tasmota/ESPHome/WLED `.bin` → flash selected
   - If *"write blocked (overlaps running slot)"* → use **"Relocate to ota_1"**, reboot, retry
   - Known-flaky: expect several attempts, power-cycle between tries (issues #47, #48)
3. **If WF864/EMW3091/MX1290 → stop.** No Tasmota/ESPHome/LibreTiny target exists for
   MX1290. Use the local-UDP HA integration and keep the bulb stock. Do not waste time on
   the UART pads; there is nothing to flash *to*.

## 7. Sources
- https://github.com/HamzaETTH/SengledTools (+ issues #37, #42, #47, #48)
- https://templates.blakadder.com/sengled_W31-N15.html
- FCC: 2AGN8 grantee index; 2AGN8-WF861/WF862/**WF863**/**WF864**/WF866/WF867; P53-EMW3091
  (internal + external photo exhibits rendered locally → `research/img/`)
- https://manuals.plus/sengled/wf864-sengled-wifi-module-manual (MX1290 specs)
- https://inside.lighting/news/25-06/smart-lighting-cloud-failure-leaves-users-dark
- https://us.amazon.com/dp/B097CYHRZJ

---

# ROUND 2 — follow-up from team-lead (live SoftAP confirmed genuine Sengled)

### Finding 9 — Complete FCC sweep of grantee 2AGN8. There is NO BR30 Wi-Fi filing.
I pulled the full grant list (53 IDs). The entire **Wi-Fi** portion of Sengled's FCC estate:

**Bulb/product-level grants (only 4):**
- `2AGN8-W1ENC1` — Sengled Smart Wi-Fi LED — 2021-05-27 — **confirmed ESP8266** (community
  flashed Tasmota on it, SengledTools issue #48)
- `2AGN8-W17N11` — Sengled Smart Wi-Fi LED — 2021-06-03 — internal photos pulled; module is a
  ~14mm board with QFN + crystal + **u.FL test connector**; silkscreen unreadable at the
  source resolution (FCC exhibit photos are genuinely low-res, ~170px wide originals)
- `2AGN8-W2GN84` — "WIFI Backlights with Camera" — not a bulb
- `2AGN8-W71N15` — Sengled smart Wifi bulb — 2024-12-03

**Module-level grants (7):** WF861, WF862, **WF863**, **WF864**, WF866, WF867, SLMB01

> **Answering the lead's request directly: "check FCC internal photos for Sengled BR30 Wi-Fi
> color specifically" — that filing does not exist and cannot be made to exist.** Sengled uses
> **modular approval**: the radio is certified once as WF86x, and the bulb that hosts it needs
> no grant of its own. That is exactly why the bulb's body prints *"Contains FCC ID:
> 2AGN8-WF86x"*. **The module filing IS the BR30's filing.** No amount of further FCC digging
> will produce a BR30-specific internal photo.

### Finding 10 — ⚠️ TRAP: WF864 (MX1290) silkscreens ESP-LOOKING pin names
This is the most important thing I found this round, and it directly undercuts the "IO0 ⇒ ESP"
inference. From the FCC external-photo silkscreen I rendered:

| | WF863 (**ESP8266EX**) | WF864 (**MXCHIP MX1290**) |
|---|---|---|
| Pin silkscreen | `3V3 IO0 IO2 ADC IO16 TX RX GND` | `ADC IO16 IO5 GND 3V3 Tx Rx BOOT TOUT` |
| Bootstrap pad | **`IO0`** | **`BOOT`** |

`ADC`, `IO16`, `IO5` and `TOUT` are *Espressif* pin names — yet they are printed on the
**MX1290** module. Sengled reused its ESP-era pin nomenclature on the MXCHIP board. So
"it has ESP-style pin labels" proves nothing.

> **The real silkscreen discriminator is `IO0` vs `BOOT`:**
> **`IO0` present → WF863 → ESP8266 → flashable.**
> **`BOOT` present and no `IO0` → WF864 → MX1290 → dead end.**

And to close the lead's two named hypotheses: **neither will appear.** `TYWE3S`/`TYWE2S` and
`WB3S`/`WB2S`/`CB3S` are **Tuya** module part numbers — Sengled has never used a Tuya module,
and `CEN` is a Beken/Realtek reset pad that will not be present either. The marking that will
actually be there is `M/N: WF86x`.

### Finding 11 — 🏆 THE ACTUAL ANSWER: the bulb TELLS YOU. No teardown, no silkscreen.
I cloned the tool and read its source. During pairing the bulb publishes its own identity to
MQTT topic **`wifielement/<MAC>/status`**, and `sengled_tool.py` prints it under a
**"Device Attributes"** heading (`sengled/wifi_setup.py:511-523`):

- **`typeCode`** → the model number, e.g. `W31-N15` ← *this is the very `W__-N__` code I could
  not obtain from Amazon or Sengled's site*
- **`identifyNO`** → the module/chip string. The tool literally tests it with
  `if "ESP8266" in identify_no.upper()` (`sengled/constants.py:26`).

**So: run `python sengled_tool.py --setup-wifi`, pair the bulb, and read the two lines it
prints.** That resolves model *and* chip in one shot, with the bulb fully assembled. Issue #47
corroborates: *"the tool ID's it as an ESP8266."*

**Heads-up on the gate:** the tool's `SUPPORTED_TYPECODES` is only `{W31-N11, W31-N15}`
(`sengled/constants.py:17-20`). A BR30 will not be in that set, so it will classify as:
- `identifyNO` contains ESP8266 → category **`untested`** → warns, proceed with **`--force-flash`**
- otherwise → **`not_supported`** → believe it; that means MX1290.

## Revised recommendation (supersedes §3 above)
1. **Run the tool and read `typeCode` + `identifyNO`.** ← do this, it costs nothing
2. Only if that fails: read `M/N: WF86x` on the module's bottom silkscreen
3. Only if that fails: antenna shape (white ceramic = ESP · etched trace = MX1290),
   or `IO0` vs `BOOT`

Odds unchanged at **~45% ESP8266EX / ~45% MX1290 / ~10% other** — but the question is now
cheap to settle empirically, so further desk research has negative expected value.
