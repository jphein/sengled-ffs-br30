# Sengled "FFS" 7.5W BR30 Color Bulb — Local Control & Open Firmware

Field notes for taking the **Sengled BR30 RGBCW WiFi bulb** (Amazon **ASIN B097CYHRZJ**,
listed as *"Updated FFS Smart Bulb … 65W Equivalent, 7.5W, Color Changing, 2.4GHz WiFi Only,
No Hub Required"*) **fully local** — no vendor cloud, integrated into Home Assistant.

> **Why this repo exists:** Sengled's cloud died in 2025. These bulbs are not Tuya devices, so
> every "flash your smart bulb over the air" guide on the internet does **not** apply to them.
> This is the guide for the hardware you actually have.

**Status:** 🚧 Active research. Sections marked 🚧 are still being confirmed on real hardware.

---

## TL;DR — pick your path

| | Path | Works when | Effort | Result |
|---|---|---|---|---|
| **A** | **Local Sengled server** (no flashing) | **Any** WiFi Sengled bulb | Low — software only | Stock firmware, re-pointed at your own MQTT server. Full local control. |
| **B** | **UART flash → ESPHome / Tasmota** | Module is **ESP8266EX** (Sengled **WF863**) | High — teardown + soldering | Native ESPHome/Tasmota device. No vendor code at all. |
| **C** | ~~OTA flash (tuya-convert / tuya-cloudcutter)~~ | **Never — see below** | — | ❌ Impossible on this hardware. |
| **D** | ~~UART flash → OpenBeken~~ | **Never — no Beken silicon here** | — | ❌ Not applicable. |

**Recommendation: start with Path A.** It is reversible, requires no teardown, no mains work,
and works regardless of which module revision is inside your bulb. Only go to Path B if you
want the vendor firmware gone entirely *and* you have confirmed an ESP8266EX module.

---

## 1. Hardware identification

### "FFS" is not a brand

The listing title reads *"Updated **FFS** Smart Bulb"*. **FFS = Amazon Frustration-Free Setup**
(Wi-Fi Simple Setup — zero-touch provisioning against an Echo already on your network). There is
no "FFS" manufacturer to chase. **The brand really is Sengled.**

### This is genuine Sengled, not a Tuya rebadge — *high confidence*

- Sengled Co., Ltd. holds its **own FCC grantee code `2AGN8`** (54 grants, 2016–2025), covering a
  whole family of **self-designed WiFi modules**.
- Sengled ran its own cloud, its own *Sengled Home* app, its own OTA, and its own MQTT/UDP
  protocol — **not** Smart Life / Tuya.
- **Consequence: `tuya-convert` and `tuya-cloudcutter` are structurally useless here.** They are
  exploits against *Tuya's* SDK and *Tuya's* OTA endpoint. There is no Tuya SDK on this device to
  attack. See [§4](#4-why-over-the-air-flashing-is-off-the-table).

### Sengled's WiFi module family (FCC grantee `2AGN8`)

| Module | FCC ID | Granted | Silicon | Flashable? |
|---|---|---|---|---|
| WF861 | `2AGN8-WF861` | 2020-11-02 | 🚧 unconfirmed | 🚧 |
| WF862 | `2AGN8-WF862` | 2021-04-05 | 🚧 unconfirmed | 🚧 |
| **WF863** | `2AGN8-WF863` | 2021-04-20 | **Espressif ESP8266EX** | ✅ **yes** |
| **WF864** | `2AGN8-WF864` | 2021-06-11 | **MXCHIP MX1290** (ARM Cortex-M4F, 133 MHz) | ❌ no |
| WF866 | `2AGN8-WF866` | 2022-11-14 | 🚧 unconfirmed | 🚧 |
| WF867 | `2AGN8-WF867` | 2022-03-02 | 🚧 unconfirmed | 🚧 |
| SLMB01 | `2AGN8-SLMB01` | 2024-06-12 | 🚧 unconfirmed | 🚧 |

Also seen in the wild on some Sengled RGBW models: an **MXCHIP EMW3091** module (silicon
unconfirmed, but MXCHIP ⇒ not an ESP ⇒ not flashable with community tooling).

> **There is no Beken BK7231T/BK7231N, no Realtek RTL8710/RTL8720, and no Tuya WB3S/CB3S/TYWE3S
> anywhere in the Sengled line.** The common heuristic *"cheap 2023+ RGBCW bulb ⇒ BK7231N"* does
> **not** hold, because this is a first-party brand shipping in-house modules.

### How to tell which module *your* bulb has

🚧 *Confirmation on real hardware pending.* The reliable method is a teardown and reading the
silkscreen on the RF module (`WF863`, `WF864`, `EMW3091`, …). The owner's teardown of this ASIN
shows a module with **`UART` silkscreened on it**, which is consistent with the Sengled WF-series
debug pinout.

Known model-code mapping from the community tooling:

| Sengled model | Type | Module / chip | Flashable? |
|---|---|---|---|
| W31-N15 | RGBW | WF863 / ESP8266EX | ✅ |
| W31-N11 | White | WF863 / ESP8266EX | ✅ |
| W21-U23 | RGBW | ESP8266EX | ✅ |
| W12-N15 | White | WF864 / MX1290 | ❌ |
| W21-N13 | RGBW | MXCHIP EMW3091 | ❌ |
| W11-N13 | RGBW | MXCHIP EMW3091 | ❌ |
| **BR30 7.5W RGBCW (B097CYHRZJ)** | RGBCW | 🚧 **to be confirmed** | 🚧 |

---

## 2. Background: the Sengled cloud is dead

This is not a you-problem. The backend is gone.

- **2025-06-18** — Sengled's cloud went down hard. WiFi bulbs stopped responding via the app,
  Alexa, and Google. Outages recurred through July 2025.
- **2025-08-01** — Amazon **permanently discontinued the Sengled Alexa skill**, citing
  *"repeated extended service interruptions."*
- Sengled was reportedly in financial crisis through 2025 — staff unpaid since January, strikes
  by April.

The bulbs themselves are fine. They are just calling a phone number that no longer answers.
**Both paths below are about giving them a number that does.**

---

## 3. Path A — local Sengled server (no flashing) ✅ recommended first

Keep the stock firmware; stand up a **local replacement for Sengled's cloud** and re-pair the
bulbs to it. Works on **all** WiFi ("No Hub Required") Sengled bulbs regardless of module — which
is exactly what this ASIN is.

### Components

| Tool | Role |
|---|---|
| [`FalconFour/ha-sengled-local`](https://github.com/FalconFour/ha-sengled-local) | Home Assistant integration + add-on. Runs a local Sengled server (MQTT) — *"brings your Sengled smart bulbs back to life after Sengled shut down their cloud servers."* |
| [`HamzaETTH/SengledTools`](https://github.com/HamzaETTH/SengledTools) | Pairing/provisioning tool. Points the bulb at your server instead of Sengled's. Also offers a direct local **UDP** HA integration and a `sengled_tool.py` CLI. |

### Outline

1. Install the **`ha-sengled-local`** add-on + integration in Home Assistant (HACS or manual).
2. Note the add-on's two endpoints — its **`/bimqtt`** URL and its **`accessCloud.json`** URL.
3. Run **`SengledTools`** and point its onboarding at *those* URLs instead of Sengled's cloud.
4. Factory-reset the bulb (power cycle sequence) so it re-enters pairing mode, then provision it
   with your WiFi credentials via SengledTools.
5. The bulb connects to **your** MQTT broker. Home Assistant discovers it as a light entity.

🚧 *Exact click-path, reset timing, and the add-on config block are being verified — see
[`research/02-ota-path.md`](research/02-ota-path.md) and
[`research/04-ha-endstate.md`](research/04-ha-endstate.md).*

### Trade-offs

**Good:** No teardown. No mains exposure. Reversible. Module-agnostic. Survives all 8 bulbs
identically.
**Bad:** You are still running Sengled's closed firmware. No ESPHome-level customization, no
effects engine, and any firmware bug is permanent.

---

## 4. Why over-the-air flashing is off the table

For completeness, because this is the first thing everyone tries:

### `tuya-cloudcutter` — two independent disqualifications

1. **Wrong silicon.** Supported chips are **Beken BK7231T / BK7231N** (unpatched), **Realtek
   RTL8710BN** (unpatched, SDK 2.0.0 excluded), and **RTL8720CF** (with caveats). The upstream
   docs are explicit: **ESP8266 / ESP8285 and other chipsets are NOT supported.** LibreTiny puts
   it bluntly — *"This currently applies to BK7231T and BK7231N only. `tuya-cloudcutter` can't be
   used for other chips."*
2. **Wrong vendor entirely.** Even if the silicon matched, cloudcutter attacks the **Tuya SDK**.
   This bulb does not run Tuya firmware.

Also worth knowing if you own actual Tuya gear: **Tuya patched the SDK in February 2022.** Any
device built against a patched SDK is not exploitable. Known-patched BK7231N firmware versions
include 1.1.2, 1.1.12, 1.1.15, 1.3.3, 1.3.8, 1.3.10, 1.5.10, and 2.0.15.

### `tuya-convert`

Same reasoning, older exploit: it hijacks a **Tuya** OTA endpoint that this device never contacts.

### Sengled's own OTA

Sengled shipped its own OTA channel — but it was served from the cloud that is now dead, and it
only ever accepted Sengled-signed images. Not a path.

> **Net: flashing this bulb is physical/serial only.** There is no software-only reflash.

---

## 5. Path B — UART flash to ESPHome / Tasmota (ESP8266EX only)

Only attempt this after confirming an **ESP8266EX (WF863)** module. On MX1290/EMW3091 hardware
there is no community firmware to flash and you will simply brick the bulb.

### ⚠️ MAINS SAFETY — READ BEFORE YOU TOUCH ANYTHING ⚠️

> ### 🛑 THE BULB MUST BE UNPLUGGED FROM MAINS. ALWAYS. NO EXCEPTIONS.
> ### 🛑 NEVER connect a USB serial adapter to the bulb while the driver board is energized from AC.

**This is not boilerplate.** A smart bulb's driver is a **non-isolated (transformerless)
switch-mode power supply**. There is **no transformer and no optocoupler** between the AC line and
the low-voltage logic:

- The board's "GND" / 0 V node is **not earth**. It is typically tied to the **rectified mains
  negative rail**, which sits at up to **−170 V DC** (US 120 V AC peak) relative to neutral, and
  can be at **full line potential** depending on socket polarization.
- Your USB serial adapter's GND is bonded to your **PC's USB ground**, which on a desktop is
  bonded to **earth through the PSU**.
- Connecting the two while AC is applied puts **mains potential across your adapter, your USB
  port, your motherboard, and anything you are touching.** The typical outcome is a destroyed
  adapter and PC. The atypical outcome is electrocution.

**The rules, in order:**

1. **UNPLUG the bulb from mains.** Remove it from the socket entirely. Do not "just switch it off
   at the wall" — a switched neutral leaves the board live.
2. **Wait ≥ 60 seconds** after unplugging before touching the board. The bulk electrolytic
   capacitor (typically 6.8–22 µF / 400 V) holds a lethal charge. **Verify with a DMM in DC volts
   across the bulk cap: it must read < 5 V** before you touch anything. If it holds charge, bleed
   it through a **10 kΩ / ≥ 2 W resistor** — not a screwdriver, which welds and shatters.
3. **Physically separate the LED/driver board from the RF module before flashing** where possible,
   or at minimum confirm no AC path exists. Safest posture: the driver board is **disconnected
   from any AC source and powered only by your bench 3.3 V**.
4. **The module is powered ONLY from your 3.3 V source during flashing.** Never energize the
   driver's AC input and the serial adapter at the same time. Not for "just a second."
5. **To observe the bulb running under mains** (e.g. capturing UART logs from a live device) you
   need a **mains isolation transformer** *and* a **galvanically isolated USB-serial adapter**
   (opto/digital-isolated, e.g. ADuM-based). Do not improvise this. For flashing you do not need
   it — just keep AC off.
6. **Never touch the board with one hand on a grounded object.** One-hand rule if AC has ever been
   near the bench.
7. **Do not power a non-isolated driver board from a bench supply's AC-side terminals.**

> **One-line version: adapter ON ⇒ mains OFF. Mains ON ⇒ adapter OFF and module disconnected.
> The two states are mutually exclusive, forever.**

### ⚠️ 3.3 V LOGIC ONLY

Both ESP8266/ESP8285 and BK7231N are **not 5 V tolerant**. If your USB-serial adapter has a
5 V / 3.3 V jumper, set it to **3.3 V and verify with a meter on the TX pin before connecting.**
**Many cheap CH340 boards ship jumpered to 5 V** and will destroy the module.

### Wiring (ESP8266EX)

| Adapter | Module |
|---|---|
| 3V3 | VCC |
| GND | GND |
| TX | RX |
| RX | TX |
| — | **IO0 → GND** to enter the bootloader (release after power-up) |

Notes carried over from the Tasmota template for the ESP8266 sibling (W31-N15):
**flashing method is "USB to Serial"**, and *"programming pins hidden behind capacitors, you may
need to fully remove the module to flash."* Budget for desoldering the module.

### Flash

```bash
# Read a full backup FIRST. Never skip this — it is your only way back.
esptool.py --port /dev/ttyUSB0 --baud 115200 read_flash 0x0 0x400000 sengled-br30-stock.bin

# Then write your firmware
esptool.py --port /dev/ttyUSB0 --baud 115200 write_flash 0x0 firmware.bin
```

Keep backups **out of git** — see [`firmware/README.md`](firmware/README.md). `.gitignore`
already excludes `*.bin` and `*_backup*`.

### Tasmota template (RGBW sibling W31-N15 — starting point, verify per-board)

```json
{"NAME":"Sengled RGBW","GPIO":[0,0,0,0,0,0,0,0,417,416,419,418,0,0],"FLAG":0,"BASE":18}
```

🚧 *An RGBCW (5-channel) template and the confirmed BR30 GPIO map for this ASIN are pending
hardware confirmation — see [`research/03-uart-flash.md`](research/03-uart-flash.md).*

### Alternative: Sengled-Rescue shim

[`SengledTools`](https://github.com/HamzaETTH/SengledTools) also ships a shim bootloader called
**Sengled-Rescue** that can chain-load Tasmota / ESPHome / WLED. Per its own compatibility matrix,
*"flashing only works with ESP8266EX-based modules (WF863)"* — the same constraint as above, but
potentially with less soldering. 🚧 *Being evaluated.*

---

## 6. Home Assistant end state

🚧 *This section is being written as research lands — see
[`research/04-ha-endstate.md`](research/04-ha-endstate.md).*

**Target:** each bulb appears in Home Assistant as a single `light` entity supporting on/off,
brightness, RGB color, and color temperature — with **zero outbound internet traffic**.

### Path A end state

Bulbs speak MQTT to your local broker via the `ha-sengled-local` add-on; the integration exposes
them as `light.*` entities. Discovery is handled by the integration.

### Path B end state (ESPHome, RGBCW)

Skeleton config — adapt pin assignments once the board is confirmed. **Note the placeholders:
never commit real credentials.**

```yaml
esphome:
  name: bulb-br30-01
  friendly_name: BR30 Bulb 01

esp8266:
  board: esp01_1m

wifi:
  ssid: !secret wifi_ssid          # -> secrets.yaml, never committed
  password: !secret wifi_password

api:
  encryption:
    key: !secret api_key
ota:
  - platform: esphome
    password: !secret ota_password
logger:

# 🚧 GPIO assignments pending hardware confirmation
output:
  - { platform: esp8266_pwm, id: ch_red,   pin: GPIO4 }
  - { platform: esp8266_pwm, id: ch_green, pin: GPIO12 }
  - { platform: esp8266_pwm, id: ch_blue,  pin: GPIO14 }
  - { platform: esp8266_pwm, id: ch_cw,    pin: GPIO5 }
  - { platform: esp8266_pwm, id: ch_ww,    pin: GPIO13 }

light:
  - platform: rgbww
    name: "BR30 Bulb 01"
    red: ch_red
    green: ch_green
    blue: ch_blue
    cold_white: ch_cw
    warm_white: ch_ww
    cold_white_color_temperature: 6500K
    warm_white_color_temperature: 2700K
```

Your `secrets.yaml` (git-ignored) looks like:

```yaml
wifi_ssid: "YOUR_WIFI_SSID"
wifi_password: "YOUR_WIFI_PASSWORD"
```

### Replicating across a batch

Flash one bulb, confirm the GPIO map and color response, **then** template the YAML per bulb
(`bulb-br30-01` … `-08`) and change only the name. With ESPHome, bulbs 2–8 can take the config
over **OTA** once the first serial flash has proven the map — so you solder once, not eight times.

---

## 7. Credits & prior art

None of this hardware would be openable without these projects. **Referenced by URL only —
nothing is vendored here.**

### Sengled-specific

- [`HamzaETTH/SengledTools`](https://github.com/HamzaETTH/SengledTools) — Sengled UDP/MQTT CLI,
  local HA integration, and the Sengled-Rescue flashing shim. The single most important source
  for this hardware.
- [`FalconFour/ha-sengled-local`](https://github.com/FalconFour/ha-sengled-local) — local
  replacement Sengled server as an HA add-on + integration.

### General smart-bulb liberation (context, mostly *not* applicable to Sengled)

- [`ct-Open-Source/tuya-convert`](https://github.com/ct-Open-Source/tuya-convert) — the original
  OTA Tuya reflash.
- [`tuya-cloudcutter/tuya-cloudcutter`](https://github.com/tuya-cloudcutter/tuya-cloudcutter) —
  Beken/Realtek OTA exploit chain.
- [`tuya-cloudcutter/tuya-cloudcutter.github.io`](https://github.com/tuya-cloudcutter/tuya-cloudcutter.github.io)
  — device database.
- [`tuya-cloudcutter/bk7231tools`](https://github.com/tuya-cloudcutter/bk7231tools) — Beken flash
  dump/analysis.
- [`libretiny-eu/libretiny`](https://github.com/libretiny-eu/libretiny) — Arduino/ESPHome support
  for BK72xx / RTL87xx.
- [`libretiny-eu/ltchiptool`](https://github.com/libretiny-eu/ltchiptool) — flashing tool for
  those chips.
- [`openshwprojects/OpenBK7231T_App`](https://github.com/openshwprojects/OpenBK7231T_App) —
  OpenBeken firmware.
- [`blakadder/templates`](https://github.com/blakadder/templates) — Tasmota device template
  database (source of the W31-N15 template above).
- [ESPHome](https://esphome.io) · [Tasmota](https://tasmota.github.io/docs/) ·
  [Home Assistant](https://www.home-assistant.io)

### Research notes

Raw working notes, with sourcing and confidence levels, are in [`research/`](research/):

| File | Topic |
|---|---|
| [`01-chip-id.md`](research/01-chip-id.md) | Chip / module identification, FCC records |
| [`02-ota-path.md`](research/02-ota-path.md) | Whether any no-solder OTA path exists |
| [`03-uart-flash.md`](research/03-uart-flash.md) | Serial flashing procedure + mains safety |
| [`04-ha-endstate.md`](research/04-ha-endstate.md) | Firmware choice + Home Assistant end state |

---

## Disclaimer

Opening a mains-powered LED bulb exposes you to **lethal voltages**, destroys the bulb's thermal
design and any warranty, and may violate local electrical regulations. Flashing third-party
firmware can permanently brick the device. **You do this at your own risk.** The authors accept no
liability for damage, injury, or death. If you are not confident reading §5 and following every
rule in it, **use Path A** — it requires no teardown at all.

## License

[MIT](LICENSE) © JP ([@jphein](https://github.com/jphein))
