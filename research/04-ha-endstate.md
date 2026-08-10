# Firmware + Home Assistant End-State — Sengled/FFS BR30 RGBCW (ASIN B097CYHRZJ)

**Status:** COMPLETE (2026-08-09 21:05→21:20 PDT)
**Sourcing:** FCC exhibit records, upstream project docs, community tooling matrices, and observation of a real bulb.
**Scope:** which firmware per chip type, ready-to-adapt ESPHome yaml, what HA sees, replicate-across-8.

## Reference environment

- Home Assistant OS, Mosquitto MQTT broker already configured
- ESPHome tooling present: local `esphome` CLI compile + dashboard at `esphome.local`
- 8 bulbs to convert

---

## ⚠️ Three corrections to the brief (verified, not inferred)

The brief carried three assumptions that the sources contradict. Flagging them first because
two of them change the recommendation.

### C1. "Tasmota also has a Beken build" — **FALSE**

Tasmota has **no** BK7231 support. Verified via the Tasmota maintainer's own discussion thread
(*"Tasmota for new Platforms — ESPHome moved to libretiny"*, arendst/Tasmota #21201) and the
OpenBeken README, which describes itself as a *"Tasmota/ESPHome **replacement**"* — i.e. it
exists precisely because Tasmota does not run there. LibreTiny ported **ESPHome** to Beken;
nobody ported Tasmota. So on Beken the real choice is ESPHome-LibreTiny **vs** OpenBeken, and
Tasmota is only a contender on the ESP8266/8285 branch.

### C2. "RGBCW = 5 PWM channels" — **probably 4-channel RGBW, and possibly not PWM at all**

Two separate problems with the 5-PWM assumption:

- **Channel count.** The only Sengled WiFi colour bulb in the Tasmota template DB is the
  **W31-N15 "Sengled RGBW"** — **4 channels, one white**, not CW+WW. Template:
  `{"NAME":"Sengled RGBW","GPIO":[0,0,0,0,0,0,0,0,417,416,419,418,0,0],"FLAG":0,"BASE":18}`
  I decoded the component IDs by hand (Tasmota packs `value = component<<5 | index`;
  `416 = 13*32+0`, and enum position 13 is `GPIO_PWM1`), which yields PWM1/2/3/4 — and the page
  confirms it independently:

  | GPIO | Tasmota | Colour |
  |------|---------|--------|
  | GPIO13 | PWM1 | **Red** |
  | GPIO12 | PWM2 | **Green** |
  | GPIO15 | PWM3 | **Blue** |
  | GPIO14 | PWM4 | **White** |

  Chip listed as **ESP8266**. Base module 18 = Generic.
  A "colour changing" bulb marketed 2000–6500K can fake colour temperature by RGB mixing, so
  the marketing copy does **not** prove a 5th channel exists. **Count the channels before
  writing the yaml.**

- **Drive topology.** Many cheap RGBCW bulbs don't wire 5 PWM lines to the MCU at all — they
  use a 2-wire (clock+data) constant-current LED driver IC. ESPHome has first-class output
  platforms for these: `sm2135`, `sm2235`/`sm2335`, `bp1658cj`, `bp5758d`, `my9231`. Relevant
  precedent: the Hackaday Sengled A19 teardown found an **SM1533E 3-channel constant-current
  driver** — i.e. Sengled *does* ship driver ICs, not only direct PWM. If you see a small
  8-pin IC near the LED pads with only two traces back to the module, it's a driver IC and the
  `esp8266_pwm` config below is the wrong shape.

### C3. The premise "once we can flash them" may not hold — and there's a no-flash path

Agent 02 established (and the Tasmota template's own flashing note corroborates) that this is
a **genuine Sengled**, not a rebadged Tuya. Consequences:

- **No tuya-cloudcutter.** It attacks Tuya's SDK; there is no Tuya SDK here. So the brief's
  "if cloudcutter worked, OTA the other 7" branch is **dead by construction** — every one of
  the 8 needs a wired first flash.
- The W31-N15 flashing note is grim: *"Ground to IO0 to prepare for flashing, **programming
  pins hidden behind capacitors, you may need to fully remove module to flash**."* Times eight.
- Sengled's cloud is dead (2025), and `FalconFour/ha-sengled-local` stands up a local
  replacement MQTT server for stock-firmware WiFi Sengled bulbs.

**This materially changes the cost/benefit — see the "honest recommendation" section.**

---

## 1. Recommended firmware, per chip

| Chip found inside | Recommend | Why | Runner-up |
|---|---|---|---|
| **ESP8266 / ESP8285** (most likely per the W31-N15 precedent) | **ESPHome**, `esp8266` platform | Native API (no MQTT hop), owner already runs the toolchain, config-as-code replicates across 8 via substitutions | Tasmota — zero compile, template DB, but adds an MQTT hop and per-device web config |
| **BK7231N / BK7231T** (if it's actually Beken) | **ESPHome via LibreTiny** (`bk72xx`) | Keeps **one** toolchain and one HA integration for all 8; LibreTiny is built into ESPHome since 2023.9 | **OpenBeken** — better exotic-hardware coverage + web UI, but MQTT + a second ecosystem to maintain |
| **MXCHIP EMW3080 / EMW3091** (real risk — newer Sengled) | **none of the three** | Proprietary MiCO OS, no open SDK, not an ESP/Beken/Realtek target | `ha-sengled-local` (keep stock fw), or physically swap the module for an ESP |

**Why ESPHome over Tasmota/OpenBeken given this owner's setup:** ESPHome's native API is
encrypted, fully local, needs no broker, and auto-discovers in HA. The MQTT broker is already
there, but adding a broker hop buys nothing here. Decisive factor: **8 identical devices**.
ESPHome's `substitutions` + `!secret` means one canonical yaml and eight 3-line wrappers, and
`esphome run` re-flashes them all over the air from the dashboard. Tasmota/OpenBeken would mean
eight web UIs configured by hand.

---

## 2. ESPHome config — ready to adapt

### 2a. Primary: 4-channel RGBW on ESP8285 (Sengled W31-N15 pinout)

Pins below are the **verified W31-N15** mapping — treat as the starting hypothesis for the
BR30, confirm per §3.

```yaml
substitutions:
  device_name: bulb-br30-1
  friendly_name: "BR30 Bulb 1"

esphome:
  name: ${device_name}
  friendly_name: ${friendly_name}

esp8266:
  board: esp8285          # 1MB flash. Use `esp01_1m` if esp8285 misbehaves.
  restore_from_flash: true

# Keep the binary SMALL — this is what makes OTA possible on 1MB flash (see §4 warning).
logger:
  baud_rate: 0            # disable UART logging; pins are sealed inside a bulb anyway

api:
  encryption:
    key: !secret api_encryption_key

ota:
  - platform: esphome     # ESPHome >=2024.6 requires the list form
    password: !secret ota_password

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  # A bulb that can't reach wifi must STILL make light. Fallback AP so it stays reachable.
  ap:
    ssid: ${device_name}-ap

captive_portal:

output:
  - platform: esp8266_pwm
    id: pwm_red
    pin: GPIO13
    frequency: 1000 Hz
  - platform: esp8266_pwm
    id: pwm_green
    pin: GPIO12
    frequency: 1000 Hz
  - platform: esp8266_pwm
    id: pwm_blue
    pin: GPIO15
    frequency: 1000 Hz
  - platform: esp8266_pwm
    id: pwm_white
    pin: GPIO14
    frequency: 1000 Hz

light:
  - platform: rgbw
    id: bulb
    name: None              # entity takes the device friendly_name; or use name: "Light"
    red: pwm_red
    green: pwm_green
    blue: pwm_blue
    white: pwm_white
    color_interlock: true   # RGB and white never on together — avoids muddy pastels
    restore_mode: ALWAYS_ON # CRITICAL for a bulb: wall switch on => light on
    default_transition_length: 400ms
```

**`restore_mode: ALWAYS_ON` is the single most important line here.** Default ESPHome restores
the previous state; a bulb that boots "off" when someone flips the wall switch reads as a dead
bulb and will get you a bug report from the household.

### 2b. If it really is 5-channel RGBCW (separate cold + warm)

Add a 5th `esp8266_pwm` output and swap the light platform. `rgbww` takes physical CW/WW
channels (the correct choice for 5 real PWM lines); `rgbct` is for hardware exposing a
*colour-temperature* pin plus a brightness pin — not this.

```yaml
light:
  - platform: rgbww
    id: bulb
    name: None
    red: pwm_red
    green: pwm_green
    blue: pwm_blue
    cold_white: pwm_cw
    warm_white: pwm_ww
    cold_white_color_temperature: 6500 K   # measure/read the bulb's own spec
    warm_white_color_temperature: 2700 K
    constant_brightness: true              # cap combined output; protects the LEDs
    color_interlock: true
    restore_mode: ALWAYS_ON
```

### 2c. If it's a driver IC (SM2135 / BP5758D / BP1658CJ) instead of PWM

Replace the whole `output:` block — no `esp8266_pwm` at all — then feed `rgbww` as in 2b.

```yaml
bp5758d:                 # or sm2135: / bp1658cj: — match the marking on the IC
  data_pin: GPIO4
  clock_pin: GPIO5

output:
  - platform: bp5758d
    id: pwm_red
    channel: 2
    current: 10          # mA — RGB typically 50, CW 30; start LOW and raise
  - platform: bp5758d
    id: pwm_green
    channel: 3
    current: 10
  - platform: bp5758d
    id: pwm_blue
    channel: 1
    current: 10
  - platform: bp5758d
    id: pwm_cw
    channel: 5
    current: 10
  - platform: bp5758d
    id: pwm_ww
    channel: 4
    current: 10
```

⚠️ Channel order on these ICs is **not** guessable and the `current:` values are a hardware
safety limit, not a preference — set them low first, confirm colours, then raise.

### 2d. If it turns out to be Beken (LibreTiny) — the bk72xx workflow

Only the platform block and the PWM platform change; `light:`, `api:`, `ota:` are identical.
This is the whole point of recommending ESPHome for both branches.

```yaml
bk72xx:
  board: generic-bk7231n-qfn32-tuya     # or cb2s / cbu / wb3s — match the module
  framework:
    version: recommended

output:
  - platform: libretiny_pwm             # NOT esp8266_pwm
    id: pwm_red
    pin: P8
    frequency: 1000 Hz
  # ... P7 / P9 / P24 etc. LibreTiny uses raw chip pin numbers (P6, P24), not D-numbers.
```

Notes verified from the ESPHome LibreTiny docs + LibreTiny flashing docs:

- LibreTiny is **built into ESPHome** since 2023.9 — no external component, `esphome compile`
  just works.
- **`TX1 (P11)` / `RX1 (P10)` are the flashing pins** and are also used by Tuya — don't
  reassign them. Default logger is `TX2 (P0)`/`RX2 (P1)`. `ADC3 (P23)` is the only ADC.
- First flash: build, then flash `firmware.uf2` with `ltchiptool` over UART-TTL.
- **OTA works after the first flash**, two ways: the device's own web page (upload the `.uf2`
  into the OTA field), or `esphome upload device.yml --device device.local`.
- **`UPK2ESPHome` solves the pin-discovery problem on Beken for free** — `ltchiptool`'s
  UPK2ESPHome tab can "Grab from ESPHome-Kickstart", or use <https://upk.libretiny.eu/> — it
  reads the *stock Tuya* config out of the device and emits a correct ESPHome yaml with the
  real GPIO mapping. **This only exists for Tuya devices**, so it will not help a genuine
  Sengled. Noting it because it's the standard answer and its absence here is exactly why §3
  is manual work.

---

## 3. How to discover the pins if the W31-N15 mapping doesn't hold

Flash a throwaway "pin-prober" config that exposes every plausible GPIO as its own dimmable
entity, then click each one in HA and write down which LED lights.

```yaml
# Candidate GPIOs on ESP8285 bulbs: 0, 2, 4, 5, 12, 13, 14, 15
output:
  - {platform: esp8266_pwm, id: p4,  pin: GPIO4}
  - {platform: esp8266_pwm, id: p5,  pin: GPIO5}
  - {platform: esp8266_pwm, id: p12, pin: GPIO12}
  - {platform: esp8266_pwm, id: p13, pin: GPIO13}
  - {platform: esp8266_pwm, id: p14, pin: GPIO14}
  - {platform: esp8266_pwm, id: p15, pin: GPIO15}

light:
  - {platform: monochromatic, name: "probe GPIO4",  output: p4}
  - {platform: monochromatic, name: "probe GPIO5",  output: p5}
  - {platform: monochromatic, name: "probe GPIO12", output: p12}
  - {platform: monochromatic, name: "probe GPIO13", output: p13}
  - {platform: monochromatic, name: "probe GPIO14", output: p14}
  - {platform: monochromatic, name: "probe GPIO15", output: p15}
```

Bring up one at a time at ~30% and note the colour. The channel count you *find* settles the
RGBW-vs-RGBCW question from §C2 — if exactly one channel produces white, it's `rgbw`; if two
whites of visibly different temperature, it's `rgbww`. **If no GPIO lights anything**, that's
the positive signal for a driver IC (§2c).

---

## 4. Replicate across 8 — the realistic workflow

The brief's "flash 1 via UART, OTA the other 7" **does not work here**: OTA requires ESPHome
already running, and with cloudcutter off the table there is no wireless way to get the first
image on. Each bulb needs its own wired flash. What OTA *does* save is **iteration** — and that
is where the real time goes.

1. **Open bulb #1, wire UART, ground IO0.** Expect to desolder the module (per the W31-N15
   note: programming pins are under capacitors).
2. **Prober config → nail the pins** (§3). Do this once, on the bench, on the one bulb that's
   already open. All 8 are identical, so this cost is paid once.
3. **Build the real config**, verify colours + `restore_mode`, on bulb #1.
4. **Wired-flash the remaining 7** with the finished config — cheaper than flashing them twice.
   Each gets a 3-line wrapper:
   ```yaml
   substitutions:
     device_name: bulb-br30-3
     friendly_name: "BR30 Bulb 3"
   packages:
     common: !include common/sengled-br30.yaml
   ```
   Put the whole config from §2a in `common/sengled-br30.yaml` minus its own `substitutions:`.
   Then `esphome run bulb-br30-3.yaml` — the shared file is the single source of truth.
5. **From then on, everything is OTA.** `esphome run <file>.yaml` picks the device over the
   network; the dashboard shows all 8 and updates them in place.

⚠️ **The 1MB-flash OTA trap (verified, and it will bite).** ESP8285 has 1MB flash, and ESPHome
OTA needs the *new* image to fit alongside the running one — so once a build exceeds roughly
**~500KB** OTA fails with *"ESP does not have enough space to store OTA file"* and you are back
to opening bulbs. A wifi+api+ota+light config fits comfortably; the way people blow the budget
is adding `web_server`, extra sensors, or `improv`. **Keep the bulb config lean and keep
`logger: baud_rate: 0`.** If you ever do exceed it, the escape hatch is to OTA a minimal
config first, then OTA the full one — not disassembly.

---

## 5. What HA sees after the flash

- **Discovery:** HA's ESPHome integration auto-discovers each device via mDNS; you confirm and
  paste the encryption key (or it's already in `!secret`). No MQTT, no broker config, no
  autodiscovery topics. Mosquitto stays uninvolved.
- **Entities:** one `light.br30_bulb_1` per bulb, plus a diagnostic RSSI/uptime sensor if added.
- **Capabilities in the more-info dialog:**
  - `rgbw` (§2a): **brightness slider + colour wheel + a white-channel slider.**
    `supported_color_modes: [rgbw]`. **No colour-temperature slider** — with one white LED
    there's no CT to tune. Warm/cool "white" must be faked by RGB mixing.
  - `rgbww` (§2b): brightness + colour wheel **+ a real colour-temp slider** bounded by the
    Kelvin values you declared. `supported_color_modes: [color_temp, rgbww]`.
  - Transitions honoured, so `light.turn_on` with `transition:` works from scripts/scenes.
- **Device page:** firmware version, IP, and an **Update entity** — new ESPHome builds show up
  as an HA update notification you can push OTA from the UI.
- **Fully local:** encrypted native API over LAN, functions with WAN down. Works in scenes,
  adaptive-lighting, voice assistants, everything that consumes a normal `light` entity.

---

## 6. Honest recommendation

**If the chip is ESP8266/ESP8285 → ESPHome, `esp8266` platform, config in §2a.** It is the
cleanest HA end-state available (encrypted-local, auto-discovered, one shared yaml for 8) and
it reuses tooling that's already running at `esphome.local`. Tasmota would work and needs no
compiler, but it routes through MQTT and configures per-device; that's the worse trade at n=8.

**If Beken → ESPHome + LibreTiny `bk72xx` (§2d)**, not OpenBeken — same toolchain, same HA
integration, and the yaml diff from §2a is about four lines.

**But weigh this against not flashing at all.** Because cloudcutter is dead here, ESPHome costs
**8 disassemblies with probable module desoldering**. `FalconFour/ha-sengled-local` gets stock
bulbs into HA over MQTT with **zero** hardware work. The trade:

- `ha-sengled-local` — hours not weekends, no risk of 8 bricked bulbs, but depends on a
  reverse-engineered server and the bulbs keep their stock firmware.
- ESPHome — permanent, first-class, no dependency on anyone's cloud *or* anyone's
  reimplementation of it. The bulb becomes a device you own outright.

My read: **try `ha-sengled-local` first, on zero bulbs' worth of solder.** If it works, you're
done. If it's flaky or unmaintained, ESPHome is the durable answer and §2–§4 is the playbook —
and in that case flash *one* bulb end-to-end before committing the other seven.

**Blocking unknown:** if the module is **MXCHIP EMW3080/EMW3091**, ESPHome/Tasmota/OpenBeken
are all impossible and `ha-sengled-local` (or a module swap) is the only route. Confirm the
module marking before buying any solder time.

---

## Sources

- [ESPHome — LibreTiny platform](https://esphome.io/components/libretiny/)
- [LibreTiny — Flashing ESPHome](https://docs.libretiny.eu/docs/flashing/esphome/)
- [LibreTiny — Beken BK72xx](https://docs.libretiny.eu/docs/platform/beken-72xx/)
- [Tasmota discussion #21201 — "ESPHome moved to libretiny"](https://github.com/arendst/Tasmota/discussions/21201)
- [OpenBK7231T_App (OpenBeken)](https://github.com/openshwprojects/OpenBK7231T_App)
- [digiblur — Tuya CloudCutter with ESPHome BK7231 guide](https://digiblur.com/2023/08/19/updated-tuya-cloudcutter-with-esphome-bk7231-how-to-guide/)
- [Tasmota template — Sengled RGBW W31-N15](https://templates.blakadder.com/sengled_W31-N15.html)
- [Tasmota templates — bulbs by type](https://templates.blakadder.com/bulb-type.html)
- [ESPHome — rgbww light](https://esphome.io/components/light/rgbww/)
- [ESPHome — BP5758D output](https://esphome.io/components/output/bp5758d/)
- [ESPHome — BP1658CJ output](https://esphome.io/components/output/bp1658cj/)
- [ESPHome — SM2135 output](https://esphome.io/components/output/sm2135/)
- [Hackaday — Sengled A19 teardown (EMW3091 + SM1533E)](https://hackaday.io/project/203358-sengled-a19-smartbulb-teardown-and-custom-firmware)
- [ESPHome issue #6420 — OTA "not enough space" on small flash](https://github.com/esphome/issues/issues/6420)
- [ESPHome feature-request #2397 — improve OTA for small flash](https://github.com/esphome/feature-requests/issues/2397)
