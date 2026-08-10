# Chip ID Research — "FFS / Sengled" BR30 RGBCW WiFi Bulb (ASIN B097CYHRZJ)

**Status:** IN PROGRESS (started 2026-08-09 21:03 PDT)
**Sourcing:** compiled from FCC records, upstream project docs, and community tooling matrices.

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
- Consequence: **tuya-convert / OTA-over-the-air flashing does NOT apply.** There is no
  Tuya `ESP_RTOS_SDK` OTA endpoint to hijack. Flashing is physical/serial only.

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


