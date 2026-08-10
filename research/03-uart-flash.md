# UART / Serial Flashing Procedure — WiFi RGBCW Smart Bulb (ASIN B097CYHRZJ)

**Status:** COMPLETE (2026-08-09 21:20 PDT)
**Sourcing:** FCC exhibit records, upstream project docs, community tooling matrices, and observation of a real bulb.
**Target:** "FFS / Sengled" 7.5W BR30 RGBCW 2.4 GHz WiFi bulb. WiFi module has `UART` silkscreened.
**Chip not yet confirmed** — two complete procedures below. **Do Section 1 (ID) first**; it takes
five minutes and picks the procedure for you.

- **Procedure A** — Espressif ESP8285 / ESP8266 → Tasmota / ESPHome (`esptool`)
- **Procedure B** — Beken BK7231N / BK7231T → OpenBeken / ESPHome-LibreTiny (`ltchiptool`)

**Everything in this document was verified** against locally installed tooling
(`esptool 5.3.1`, `ltchiptool 4.14.4`, `bk7231tools`, `esphome 2026.7.4`) and against vendor /
project documentation. Where the original brief was wrong, this document says so and cites the
correction.

---

# ⚠️ SECTION 0 — MAINS SAFETY. READ THIS FIRST. ⚠️

> # 🛑 **THE BULB MUST BE UNPLUGGED FROM MAINS. ALWAYS. NO EXCEPTIONS.**
>
> # 🛑 **NEVER connect a USB serial adapter to the bulb while the driver board is energized from AC.**

**Why this is not boilerplate:**

A smart bulb's driver is a **non-isolated (transformerless) switch-mode power supply**. There is
**no transformer and no optocoupler** between the AC line and the low-voltage logic. That means:

- The board's "GND" / 0 V node is **not earth**. It is typically tied to the **rectified mains
  negative rail**, which sits at up to **−170 V DC** (US 120 V AC peak) relative to neutral, and can
  be at **full line potential** depending on socket polarity.
- Your USB serial adapter's GND is bonded to your **PC's USB ground**, which on a desktop is bonded
  to **earth through the PSU**.
- Connecting the two while AC is applied puts **mains potential across your adapter, your USB port,
  your motherboard, and anything you are touching.** The typical outcome is a destroyed adapter and
  PC. The atypical outcome is electrocution.

**The rules, in order:**

1. **UNPLUG the bulb from mains.** Remove it from the socket entirely. Do not "just switch it off at
   the wall" — a switched-neutral fixture leaves the board live.
2. **Wait ≥60 seconds** after unplugging before touching the board. The bulk electrolytic capacitor
   (typically 4.7–22 µF / 400 V) holds a lethal charge. **Verify with a DMM in DC volts across the
   bulk cap: it must read < 5 V** before you touch anything. If it holds charge, bleed it through a
   **10 kΩ / ≥2 W resistor** — not a screwdriver, which welds and shatters.
3. **The module is powered ONLY from your 3.3 V source during flashing.** Never energize the driver's
   AC input and the serial adapter at the same time. Not for "just a second."
4. **Physically separate the RF module from the mains section** where practical, or at minimum
   confirm there is no AC path. Safest posture: the driver board is **disconnected from any AC source
   and only your bench 3.3 V is present.**
5. **If you must observe the bulb running under mains** (capturing UART logs from a live device), you
   need a **mains isolation transformer** AND a **galvanically isolated USB-serial adapter**
   (ADuM/opto-isolated). Do not improvise this. For flashing you do not need it — just keep AC off.
6. **One-hand rule.** Never touch the board with your other hand on a grounded object.
7. **Do not "just test the LEDs" mid-procedure.** Reassemble fully, disconnect the adapter completely
   (both data and power), *then* apply mains.

> **The one-line version: adapter ON ⇒ mains OFF. Mains ON ⇒ adapter OFF and disconnected.
> The two states are mutually exclusive, forever.**

### ⚠️ Second warning: 3.3 V LOGIC ONLY

> **Both ESP8285 and BK7231N are NOT 5 V tolerant.** If your USB-serial adapter has a 5 V / 3.3 V
> jumper, set it to **3.3 V** and **verify with a meter on the adapter's TX pin** before connecting
> anything. Many cheap CH340 boards ship jumpered to 5 V, and some FTDI clones have a jumper that
> only switches the VCC output while leaving the **signal** lines at 5 V — measure, don't assume.
> A 5 V TX line will damage the module.

### ⚠️ Third warning: the adapter's 3.3 V pin is probably not enough power

Espressif's own docs: *"For stable use of the ESP8266 a power supply with 3.3 V and ≥ 250 mA is
required"* and *"using the power available from USB-to-Serial adapter is not recommended, these
adapters typically do not supply enough current."* The FTDI internal regulator in particular is
rated far below what an ESP's TX burst draws (~350 mA peak). LibreTiny says the same thing about
BK7231: *"using a good, stable 3.3 V power supply is crucial"* — most flashing failures are
brownouts, not protocol errors.

**Practical guidance:**

| Source | Verdict |
|---|---|
| CH340/CP2102 board's 3V3 pin, no other load | *Sometimes* works. Try it, but suspect it first when things fail. |
| FTDI FT232RL 3V3 pin | **Usually insufficient.** Expect failures. |
| Bench supply @ 3.3 V, ≥500 mA | **Recommended.** |
| AMS1117-3.3 module fed from the adapter's 5 V pin, with 10 µF + 100 nF at the module | **Recommended and cheap.** |

If you use an external 3.3 V supply: **tie its GND to the adapter's GND**, and do **not** also
connect the adapter's 3V3 pin (avoid back-feeding two regulators into each other).

---

# SECTION 1 — IDENTIFY THE CHIP (do this first)

The module in a Tuya-ecosystem bulb is a small daughtercard soldered to the driver board. Its
markings tell you almost everything.

### 1.1 Read the module part number

Look on the module's top face (under the RF can, or silkscreened on the PCB edge). Cross-reference:

| Module | Chip | Family | Procedure | Flash |
|---|---|---|---|---|
| **TYLC5 / TYLC5E** | **ESP8285** | Espressif | **A** | **1 MB** |
| **TYWE3S / TYWE2S / TYWE3L / TYWE2L** | **ESP8266/ESP8285** | Espressif | **A** | 1–2 MB |
| **ESP-01D / ESP-02S / ESP8285-xx** | **ESP8285** | Espressif | **A** | 1–2 MB |
| **CBLC5** | **BK7231N** | Beken | **B** | 2 MB |
| **CB3S / CB2S / CB1S / CB3L / CB2L / CB3SE / CBU** | **BK7231N** | Beken | **B** | 2 MB |
| **WBLC5** | **BK7231T** | Beken | **B** (see B.0) | 2 MB |
| **WB3S / WB2S / WB1S / WB3L / WB2L** | **BK7231T** | Beken | **B** (see B.0) | 2 MB |
| **WB2L_M1** | **BK7231N** | Beken | **B** | 2 MB |
| **WBR3 / WR3 / CR3L / BW15** | RTL87xx (Realtek) | Realtek | *neither* — LibreTiny `realtek-*`, see B.9 | 2–4 MB |
| **T1-2S / T1-3S / T1-U / T1-M** | BK7238 | Beken | **B** variant, family `bk7238` | 2 MB |
| **LN-CB3S / WL2S / LN-02** | LN882H | Lightning | *neither* — LibreTiny `ln882h`, see B.9 | 2 MB |

> ### 🔧 CORRECTION TO THE BRIEF
> The task brief said *"BK7231N (WB3S/CB3S)"*. **This is wrong for WB3S.**
> - **WB3S = BK7231T** — the *older* variant, and it is the **dangerous-to-brick** one.
> - **CB3S = BK7231N.**
>
> Verified two ways: the Tuya CB3S datasheet states the CB3S "consists of a highly integrated RF
> chip **BK7231N**", and LibreTiny's own board database (`ltchiptool list boards`, run locally
> against v4.14.4) lists `wb3s → BK7231T` and `cb3s → BK7231N`. Getting this backwards and flashing
> a BK7231T with BK7231N parameters is a classic bricking path. **Read Section B.0 before flashing
> any `WB*` module.**
>
> Also, for a **bulb** specifically, the most likely modules are the *lighting* variants —
> **CBLC5 (BK7231N)**, **WBLC5 (BK7231T)**, or **TYLC5 (ESP8285)** — not the generic `*3S` parts.
> These are physically smaller (TYLC5 is 8.5 × 13.5 mm, 2 mm pitch, 2 rows of pins) and have
> 5 PWM/driver channels for RGBCW.

### 1.2 If the marking is gone or the can is unlabeled

Pry off the RF shield can (gentle heat + a thin blade at a corner) and read the SoC die marking
directly. `BK7231N`, `BK7231T`, `ESP8285`, `RTL8710BN` are all printed on the SoC package.

### 1.3 Electrical tell (no disassembly)

Wire up 3.3 V/GND/TX/RX (Section 2), power up, and just **listen** at 115200 8N1:

```bash
# Watch boot output — do NOT connect anything else yet.
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200
# (or) screen /dev/ttyUSB0 115200
```

- **ESP8266/ESP8285** emits its ROM boot banner at **74880 baud** (garbage at 115200), then the app
  at 115200: `ets Jan 8 2013,rst cause:...,boot mode:(3,7)`. Try `74880` explicitly to confirm.
- **BK7231x** emits nothing on UART1 (the programming port is silent by design — LibreTiny: *"No
  text output on this port"*). Logs come out of **UART2**. Silence on the programming pads at
  115200 + a legible ROM banner at 74880 ⇒ **ESP**. Total silence on both ⇒ likely **Beken**.

Then confirm definitively with the tools (both are non-destructive read-only probes):

```bash
# ESP hypothesis — auto-detects chip type:
esptool --port /dev/ttyUSB0 chip-id

# Beken hypothesis — auto-detects BK7231T vs BK7231N vs BK7238:
bk7231tools chip_info -d /dev/ttyUSB0
# or:
ltchiptool flash info bk7231n -d /dev/ttyUSB0
```

`ltchiptool flash info` reports the chip's real family regardless of what family you ask for, so it
is a safe identification probe.

---

# SECTION 2 — FINDING THE PADS (partial or missing silkscreen)

The bulb's board has `UART` silkscreened, which strongly suggests a broken-out programming header.
Typical Tuya layout is a 4-pad row: **3V3 · GND · TX1 · RX1** (sometimes with a 5th `CEN`/`RST` or
`IO0`).

### 2.1 Find GND first (always)

**Board de-energized, bulk cap verified < 5 V.** DMM in **continuity/beep** mode:

- Probe each candidate pad against the **negative terminal of the bulk electrolytic cap** or the
  **ground plane / large copper pour**. The pad that beeps is GND.
- Cross-check: GND is continuous with the metal RF shield can on nearly every Tuya module.
- Cross-check: the module's GND pin is a large pad and usually the widest trace.

### 2.2 Find 3V3

- **Diode mode**, black probe on GND: the 3V3 rail typically reads **0.4–0.7 V** (the SoC's ESD
  diodes). A floating GPIO reads similarly, so this alone is not conclusive.
- **Better:** continuity from the candidate pad to the **output pin of the on-board LDO** (a SOT-23-5
  or SOT-89 part near the module, often marked `AMS1117-3.3`, `662K`, `XC6206`, or a 4-pin
  `ME6211`). The 3V3 pad beeps against the LDO output.
- **Best:** with only your **external** 3.3 V applied to what you believe is 3V3/GND, measure at the
  module's own VCC pin — should read 3.3 V ± 0.1 V.
- **Never guess-and-apply.** If you power a GPIO with 3.3 V while VCC is unpowered, you back-feed the
  die through its protection diode. Confirm continuity to the LDO *before* applying power.

### 2.3 Distinguish TX from RX

Two reliable methods:

1. **Voltage at idle.** With the module powered and running (3.3 V applied, no adapter connected):
   the **module's TX** idles **high at ~3.3 V** (UART mark state). The **module's RX** is an input
   with a weak/absent pull and typically sits high too but is far more easily pulled — probe with a
   10 kΩ to GND: TX holds near 3.3 V (it's an active driver), RX collapses toward 0 V.
2. **Trace continuity to the module pin.** ESP: TX = pin marked `TX`/`U0TXD`/`TP3`; BK7231:
   **TX1 = P11**, **RX1 = P10** (LibreTiny/Tuya pin definitions, cross-checked against the ESPHome
   `cblc5` board table: `TX1: 11, RX1: 10`). Beep from the pad to the module's castellated pin.
3. **Just try it.** Crossing TX/RX is **not damaging** — you simply get no response. If the tool
   times out, swap the two wires and retry. This is the fastest test and costs nothing.

> ⚠️ **But do not cross TX/RX during a Beken *write*.** A community report notes that crossed lines
> during an erase/write window can leave flash blank and the module in a reboot loop. Establish a
> working *read* first (Section B.4) — that proves the wiring — and only then write.

### 2.4 CROSS-OVER — the wiring rule

> **Module TX → Adapter RX**
> **Module RX → Adapter TX**
> **GND → GND** (always, and always connect GND first / disconnect it last)
> **3V3 → 3V3** (only if you're powering from the adapter — see Section 0's third warning)

### 2.5 In-place vs desoldered

| | **In-place (module still on driver board)** | **Desoldered module** |
|---|---|---|
| Effort | Low — tack 4 wires to the `UART` pads | High — hot air, risk of pad lift |
| Mains risk | **Higher** — the mains section is physically attached; a stray reconnection is a real hazard | **Lower** — no mains section present at all |
| Power | The driver's LDO is present but unpowered; you inject 3.3 V directly at the module's 3V3 | You must supply 3.3 V yourself |
| Load | Driver ICs (BP5758D / SM2135 / SM2235) may load the rail and share GPIOs; usually harmless | None |
| **Recommendation** | **Do this.** It's what everyone does, and it works. | Only if in-place flashing fails, or you want maximum mains isolation. |

**In-place is fine and is the normal approach — provided the bulb is unplugged and the bulk cap is
discharged (Section 0).** The single most common reason to prefer desoldering is that some driver
boards pull GPIO0 (ESP) or CEN (Beken) via components that fight your boot-mode strap. If boot-mode
entry refuses to work in-place, lift just that one pin rather than the whole module.

**Practical soldering notes:**
- Tack **30 AWG silicone wire** or use spring-loaded pogo pins / a "needle" test clip.
- Strain-relieve with a blob of hot glue or Kapton — a wire that rips a pad mid-flash is how modules
  die.
- Keep leads **short (< 15 cm)** — long unshielded UART at 921600 baud is unreliable.

---

# PROCEDURE A — ESP8285 / ESP8266 → Tasmota or ESPHome

## A.0 Prerequisites

Already installed on this machine (verified):

```
esptool 5.3.1   (pipx, at ~/.local/bin/esptool)
esphome 2026.7.4 (pipx)
```

Nothing to install for Procedure A. If you need esptool elsewhere:

```bash
pipx install esptool          # or: pip install --user esptool
```

> **esptool v5 syntax note:** v5 replaced all underscores with dashes. It is
> `read-flash`, `write-flash`, `erase-flash`, `flash-id`, `chip-id` —
> **not** `read_flash`/`write_flash`. Most tutorials on the web (including the Tasmota docs) still
> show the v4 underscore form; translate them. Verified against the local `esptool --help` output.

Serial access: JP is already in the `dialout` group, and `ch341`, `cp210x`, `ftdi_sio`, `pl2303`
kernel modules are all present. The adapter will enumerate as `/dev/ttyUSB0`.

## A.1 Pinout and wiring

For a **TYLC5** (the ESP8285 bulb module — 8.5 × 13.5 mm, 2 mm pitch), the programming signals are on
**test points**, not the main pin rows (per the Tuya TYLC5 datasheet):

| Signal | TYLC5 location | Purpose |
|---|---|---|
| **VCC (3.3 V)** | Pin 6 | Power |
| **GND** | Pin 2 | Ground |
| **U0TXD** | **TP3** | Module TX → adapter RX |
| **U0RXD** | **TP4** | Module RX → adapter TX |
| **GPIO0** | **TP2** | **Pull to GND to enter flash mode** |
| **RST** | **TP1** | Active-low hardware reset |
| GPIO12 / GPIO14 / GPIO4 | Pins 3 / 4 / 5 | LED channels (G / R / W typical) |

For a **TYWE3S / TYWE2S**-class module the pads are labeled on the module edge: `3V3`, `GND`, `RX`,
`TX`, `IO0`/`GPIO0`, `EN`, `RST`.

> On some Tuya ESP modules **GPIO0 is not broken out under that name** — on TYWE2S-derived parts it
> is routed to the pad silkscreened `AD` while the rest of the pinout matches the classic layout.
> If you can't find `IO0`, check the `AD` pad, or solder a fine wire directly to the SoC's GPIO0 pin.

### Wiring table

| Adapter | Module | Notes |
|---|---|---|
| GND | GND | **Connect first, disconnect last** |
| 3V3 (or external supply +) | 3V3 / VCC | See Section 0 warning 3 |
| **RX** | **TX** (U0TXD / TP3) | ← cross-over |
| **TX** | **RX** (U0RXD / TP4) | ← cross-over |
| GND (via jumper/clip) | **GPIO0** | Boot-mode strap — see A.2 |
| — | EN / CHIP_EN | Must be **high**. Usually pulled up on-module. If dead, tie to 3V3 via 10 kΩ. |
| — | RST | Leave floating (internally pulled up), or pull low momentarily to reset. |

**Optional but very convenient:** wire adapter **DTR → module RST** and **RTS → module GPIO0**
through the standard 2-transistor auto-reset circuit *if* your adapter breaks those lines out.
Without it, everything below is a manual power-cycle, which is completely fine.

## A.2 Entering flash (download) mode

The ESP samples three strapping pins at the instant `EN`/`RST` releases:

| Pin | Flash/download mode | Normal boot |
|---|---|---|
| **GPIO0** | **LOW (0 V)** | HIGH |
| GPIO2 | HIGH | HIGH |
| GPIO15 | LOW | LOW |

GPIO2 and GPIO15 are almost always already strapped correctly on a production module. **You only
need to force GPIO0 low.**

**The sequence:**

1. Power off (disconnect the module's 3V3).
2. Short **GPIO0 to GND** (jumper wire, test clip, or just hold a probe on it).
3. Apply 3.3 V (power on).
4. **You may now release GPIO0** — the strap is only sampled at reset. Leaving it grounded for the
   whole session is also fine and is what most guides recommend.
5. Run your esptool command.
6. **After every esptool command the chip resets out of download mode.** To run a second command,
   repeat steps 1–3. (Tasmota docs: *"When the command completes the device is out of firmware
   upload mode!"*)

If GPIO0 is inaccessible: pull **RST low, then release it while GPIO0 is held low** — same effect
without cycling power.

## A.3 Detect the chip (non-destructive)

```bash
# Auto-detect chip type and MAC
esptool --port /dev/ttyUSB0 chip-id

# Read the SPI flash manufacturer/device ID and detected size
esptool --port /dev/ttyUSB0 flash-id
```

Expected on a bulb: `Chip is ESP8285...` (an ESP8266 core with 1 MB flash in-package) and
`Detected flash size: 1MB`.

> If `flash-id` reports **ESP8285**, the flash is **internal to the package** and shares
> GPIO9/GPIO10. This is exactly why **`-fm dout` is mandatory** when writing — QIO/DIO modes need
> those two pins, and using them will produce a device that flashes "successfully" and then never
> boots. **Always `--flash-mode dout` on ESP8285.**

If it can't connect: `Failed to connect to ESP8266: Timed out waiting for packet header` almost
always means (a) GPIO0 wasn't low at reset, (b) TX/RX are swapped, or (c) brownout — see Section 0
warning 3.

## A.4 ⚠️ BACK UP THE STOCK FIRMWARE FIRST (non-negotiable)

This is your only way back to a working bulb if anything goes wrong. It also preserves the factory
WiFi calibration data (the RF init blob at the top of flash) — **losing that can permanently degrade
WiFi range**, and it is not recoverable from any download.

```bash
mkdir -p ~/sengled-backups && cd ~/sengled-backups

# Full 1 MB dump (ESP8285). Use 0x200000 instead if flash-id reported 2MB.
esptool --port /dev/ttyUSB0 --baud 115200 \
  read-flash 0x0 0x100000 bulb-esp8285-stock-full.bin
```

Verify:

```bash
ls -l bulb-esp8285-stock-full.bin      # must be exactly 1048576 bytes for 1MB
sha256sum bulb-esp8285-stock-full.bin | tee bulb-esp8285-stock-full.sha256
```

> **A short dump is a failed dump.** If the file isn't exactly `0x100000` (1 048 576) bytes, do not
> proceed — re-enter download mode and read again.

**Do it twice and compare.** A dump that differs between reads means an unstable link or a marginal
power supply, and a corrupt backup is worse than no backup because you'll trust it:

```bash
esptool --port /dev/ttyUSB0 read-flash 0x0 0x100000 bulb-esp8285-stock-verify.bin
cmp bulb-esp8285-stock-full.bin bulb-esp8285-stock-verify.bin && echo "BACKUP GOOD" || echo "MISMATCH — DO NOT PROCEED"
```

**Optionally save just the RF calibration sectors separately** (last 16 KB on a 1 MB ESP8285 — this
is `esp_init_data` + system params):

```bash
esptool --port /dev/ttyUSB0 read-flash 0xFC000 0x4000 bulb-esp8285-rf-cal.bin
```

Copy the backups off this machine before you write anything.

## A.5 Build the firmware

### Option 1 — ESPHome (recommended for Home Assistant)

Create `bulb.yaml`. **Set the LED channel GPIOs to match the module.** For TYLC5-class bulbs the
common mapping is **R=GPIO14, G=GPIO12, B=GPIO13, CW=GPIO4, WW=GPIO5** — *verify against your board
before trusting it*, and see the note below about non-PWM drivers.

```yaml
esphome:
  name: bulb-br30-01
  friendly_name: BR30 Bulb 01

esp8266:
  board: esp8285          # 1 MB, no OTA-slot headroom — see note
  restore_from_flash: true

logger:
  baud_rate: 0            # free the UART; the bulb has no free pins to spare

api:
  encryption:
    key: !secret api_key
ota:
  - platform: esphome
    password: !secret ota_password
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap: {}
captive_portal:

output:
  - { platform: esp8266_pwm, id: out_r,  pin: GPIO14, frequency: 1000 Hz }
  - { platform: esp8266_pwm, id: out_g,  pin: GPIO12, frequency: 1000 Hz }
  - { platform: esp8266_pwm, id: out_b,  pin: GPIO13, frequency: 1000 Hz }
  - { platform: esp8266_pwm, id: out_cw, pin: GPIO4,  frequency: 1000 Hz }
  - { platform: esp8266_pwm, id: out_ww, pin: GPIO5,  frequency: 1000 Hz }

light:
  - platform: rgbww
    name: "Bulb"
    red: out_r
    green: out_g
    blue: out_b
    cold_white: out_cw
    warm_white: out_ww
    cold_white_color_temperature: 6500 K
    warm_white_color_temperature: 2700 K
```

Build and locate the binary:

```bash
cd ~/sengled
esphome compile bulb.yaml
ls -l .esphome/build/bulb-br30-01/.pioenvs/bulb-br30-01/firmware.bin
```

> ### 🔧 CORRECTION TO THE BRIEF
> The brief said to flash "ESPHome **factory.bin**". **There is no factory.bin for ESP8266/ESP8285.**
> Verified against the installed ESPHome 2026.7.4 source: `components/esp8266/__init__.py` declares
> the flashable artifact as **`firmware.bin`**; only `components/esp32/__init__.py` declares
> `firmware.factory.bin` (ESP32 needs a merged bootloader + partition-table + app image; ESP8266
> does not). For LibreTiny/Beken targets the artifact is **`firmware.uf2`** — see Procedure B.
>
> **ESP8266/ESP8285 → `firmware.bin` @ `0x0`.**

> **1 MB flash caveat:** a 1 MB ESP8285 cannot hold two full ESPHome/Tasmota images, so wireless OTA
> is tight-to-impossible with a large config. Keep the config lean (that's why `logger.baud_rate: 0`
> and no extra components above). Tasmota ships **`tasmota-lite.bin`** and minimal-build variants
> specifically for this. If OTA fails later, you re-flash over UART — the wires are the fallback.

**Non-PWM LED drivers:** many RGBCW bulbs do **not** drive the LEDs with SoC PWM at all. They use a
dedicated constant-current driver IC (**BP5758D**, **SM2135**, **SM2235**, **SM16716**, **BP1658CJ**)
on a 2-wire clock/data bus. If you see one of those markings on the board, **the PWM YAML above will
not work** — use ESPHome's `sm2135` / `sm2235` / `bp5758d` output platforms (or Tasmota's
corresponding `SM2135`/`BP5758D` GPIO component) and wire the *clock* and *data* GPIOs instead.
Identify the driver IC before you finalize the YAML.

### Option 2 — Tasmota

Download a build from <https://ota.tasmota.com/tasmota/release/>:

```bash
cd ~/sengled
# Full build (needs 1MB free; use tasmota-lite.bin if space is tight)
curl -fLO https://ota.tasmota.com/tasmota/release/tasmota.bin
sha256sum tasmota.bin
```

Configure the GPIOs afterwards from Tasmota's web UI (**Configuration → Configure Module**) or apply
a template from <https://templates.blakadder.com/>. Search there for your exact bulb before
inventing a template — a matching one likely exists.

## A.6 Erase and write

**Re-enter download mode** (A.2) before each command.

```bash
# 1) Erase — clears stock partitions and stale config that can confuse the new firmware
esptool --port /dev/ttyUSB0 erase-flash
```

**Re-enter download mode again**, then:

```bash
# 2a) Write ESPHome
esptool --port /dev/ttyUSB0 --baud 115200 \
  write-flash --flash-mode dout --flash-size 1MB --flash-freq 40m \
  0x0 .esphome/build/bulb-br30-01/.pioenvs/bulb-br30-01/firmware.bin

# 2b) — or — Write Tasmota
esptool --port /dev/ttyUSB0 --baud 115200 \
  write-flash --flash-mode dout --flash-size 1MB --flash-freq 40m \
  0x0 tasmota.bin
```

Short-flag equivalents (identical, verified against `esptool write-flash --help` on v5.3.1):

```bash
esptool -p /dev/ttyUSB0 -b 115200 write-flash -fm dout -fs 1MB -ff 40m 0x0 firmware.bin
```

**Why each flag:**
- **`-fm dout`** — **mandatory on ESP8285.** Its internal flash shares GPIO9/GPIO10; QIO/DIO would
  claim those pins and the device would flash cleanly then fail to boot.
- **`-fs 1MB`** — must match the real part. Verify with `flash-id` first; **`-fs detect`** also works
  and is safer if you're unsure.
- **`-ff 40m`** — conservative and universally compatible.
- **`-b 115200`** — start conservative. Once a write succeeds you can try `-b 460800` for speed. If
  you see checksum failures, drop back to 115200 before blaming anything else.

Verify the write:

```bash
esptool --port /dev/ttyUSB0 verify-flash --flash-mode dout --flash-size 1MB 0x0 firmware.bin
```

## A.7 First boot

1. **Remove the GPIO0-to-GND jumper.** (Leaving it grounded keeps the chip in the bootloader.)
2. **Fully power-cycle** — Tasmota docs specifically note *"for a proper device initialization after
   first firmware upload power down and power up the device."* A soft reset is not sufficient.
3. Watch it come up:
   ```bash
   python3 -m serial.tools.miniterm /dev/ttyUSB0 115200
   ```
   (Skip this if you set `logger.baud_rate: 0` — there will be nothing to see.)
4. Look for the fallback AP (`bulb-br30-01` for ESPHome, `tasmota-XXXX` for Tasmota), join it, and
   supply WiFi credentials.
5. **Disconnect the adapter completely — power and data — before reassembling and applying mains.**

## A.8 Restoring the stock firmware

```bash
# Re-enter download mode, then:
esptool --port /dev/ttyUSB0 write-flash --flash-mode dout --flash-size 1MB \
  0x0 ~/sengled-backups/bulb-esp8285-stock-full.bin
```

---

# PROCEDURE B — Beken BK7231N/T → OpenBeken or ESPHome-LibreTiny

## B.0 ⚠️ FIRST: which Beken variant?

This matters more than anything else in Procedure B.

| | **BK7231N** (CB3S, CBLC5, CB2S, CBU, WB2L_M1) | **BK7231T** (WB3S, WBLC5, WB2S, WB3L) |
|---|---|---|
| Boot ROM | **Has a mask-ROM download mode** | **No download-mode ROM** |
| Brickability | **Effectively unbrickable via software** — the ROM always answers | **Brickable.** If you erase the bootloader it will not talk to you again over UART. |
| Behavior | Enters download mode on any reset while a flasher is polling | *"Will exit download mode when communication with the flasher is lost"* and *"cannot be forcefully entered into download mode without active flasher communication"* |
| Practical rule | Relax. Retry freely. | **Never write to the bootloader region.** `bk7231tools write_flash` gates this behind `-B/--bootloader` and warns *"not recommended on BK7231T"* — **do not pass `-B` on a T.** |

(Source: LibreTiny BK72xx platform docs; corroborated by `bk7231tools write_flash --help`, run
locally.)

**Run `bk7231tools chip_info` (B.3) and read the reported chip before you write anything.**

## B.1 Tools to install

**Neither of these is installed on this machine.** Install both:

```bash
pipx install ltchiptool
pipx inject ltchiptool bk7231tools     # optional: keeps them in one venv
# — or, independently —
pipx install "bk7231tools[cli]"
```

The `[cli]` extra pulls in **PyCryptodome**, which is **required for Tuya Storage / key extraction**
(B.5). Without it, `dissect_dump --storage` cannot decrypt.

For the GUI (genuinely nicer for a first attempt, since it shows the link handshake live):

```bash
pipx install "ltchiptool[gui]"     # requires Python 3.10+
ltchiptool gui
```

Verified locally: `ltchiptool 4.14.4` and `bk7231tools` both install cleanly on Python 3.12 and
expose the exact command surface documented below.

## B.2 Pinout and wiring

BK7231x programming happens on **UART1**, which is **silent** — it emits no log text, only the
download protocol. (Logs, if any, come out of UART2.)

| Signal | BK7231 GPIO | Module pad | Notes |
|---|---|---|---|
| **TXD1** | **P11** | `TX1` / `TXD1` | → adapter **RX** |
| **RXD1** | **P10** | `RX1` / `RXD1` | → adapter **TX** |
| **VCC** | — | `3V3` / `VCC` | 3.0–3.6 V |
| **GND** | — | `GND` | Common ground |
| **CEN** | — | `CEN` | Chip-enable. **Pull to GND to hold in reset**; release to boot. Optional. |
| **RST** | — | `RST` (pin 1 on CB3S) | Active-low reset. Alternative to CEN. |

Verified: LibreTiny documents *"TX1: GPIO11 (P11), RX1: GPIO10 (P10)"*; the ESPHome `cblc5` board
table (read locally from `esphome/components/bk72xx/boards.py`) independently gives
`"TX1": 11, "RX1": 10, "SERIAL1_TX": 11, "SERIAL1_RX": 10`. The Tuya CB3S datasheet lists
`15 = RXD1`, `16 = TXD1`, `8 = VCC`, `9 = GND`, `3 = CEN`, `1 = RST`.

**The `WB3S`/`CB3S`/`TYWE3S` programming pads are pin-compatible with each other** — same physical
positions — which is precisely why they're so easy to confuse. Identify by *marking*, not by pad
layout.

**Wiring (cross-over, same as always):**

```
Adapter GND  ──── GND        (connect first, remove last)
Adapter TX   ──── RX1 (P10)
Adapter RX   ──── TX1 (P11)
3.3 V source ──── 3V3        (see Section 0 warning 3 — Beken is even more brownout-sensitive)
   (optional)     CEN        (a switch/jumper to GND for resetting)
```

**CEN is optional.** Community consensus and the ltchiptool docs both allow leaving CEN floating and
using a **power cycle** as the reset instead. That's the recommended approach when CEN isn't broken
out. Do **not** tie CEN permanently to GND — that holds the chip in reset forever.

## B.3 The download-mode handshake (this is the part everyone gets wrong)

**BK7231 has no "hold a button" boot mode. There is no strapping pin.** Instead:

> The **flasher must already be running and spamming link-check packets** when the chip resets. The
> ROM bootloader listens on UART1 for a very brief window right after reset. If it hears the magic
> handshake, it stays in download mode. If it doesn't, it boots the application and the window is
> gone.

I read the implementation to confirm the exact mechanism (`bk7231tools/serial/linking.py`,
`wait_for_link`): the tool sets the serial read timeout to **5 ms** and loops, sending
`BkLinkCheckCmnd` as fast as it can until it gets a valid `BkLinkCheckResp` or the link timeout
expires. Default link timeout is **10 s** for `bk7231tools`, **20 s** for `ltchiptool` (`-t`).

**So the sequence is: START THE COMMAND FIRST, then reset the chip.**

```
1. Wire everything up.  Module UNPOWERED (or held in reset via CEN→GND).
2. Run the ltchiptool / bk7231tools command.  It prints "Connecting..." and starts polling.
3. NOW reset the chip:
     • preferred:  disconnect and reconnect the 3V3 wire (a clean power cycle), OR
     • if CEN is wired: touch CEN to GND for ~200 ms, then release.
4. The tool links within a second or two and proceeds.
5. If it times out, just re-run and power-cycle again — it is not a destructive failure.
```

**On automatic reset:** `bk7231tools` *does* implement a hardware reset via the serial control lines
(`hw_reset()`: RTS high + DTR high → 100 ms → DTR low → 100 ms → RTS low). **This only helps if
those lines are physically wired to CEN/RST**, which on a bulb's tacked-on 4-wire header they are
not. Assume manual power-cycling.

**Pro tip:** put a small slide switch or a header jumper in the 3V3 line. You will power-cycle this
thing a dozen times.

### Verify the link before doing anything else

```bash
bk7231tools chip_info -d /dev/ttyUSB0
# ...then power-cycle the module.
```

Expected: it reports the chip type (`BK7231N` / `BK7231T` / `BK7238`), bootloader version, and flash
ID. **This tells you which variant you have (B.0) and proves your wiring is correct — do this before
any write.**

Equivalent with ltchiptool:

```bash
ltchiptool flash info bk7231n -d /dev/ttyUSB0
```

## B.4 ⚠️ BACK UP THE FULL FLASH FIRST (non-negotiable)

The Beken dump contains **per-device Tuya keys, the device UUID/authkey, and the RF calibration
data**. These are unique to your bulb and **cannot be re-downloaded from anywhere**. Losing them
means you can never restore stock, and can degrade WiFi performance.

```bash
mkdir -p ~/sengled-backups && cd ~/sengled-backups

# Option 1 — bk7231tools (reads the entire 2 MB by default since v1.0.0)
bk7231tools read_flash -d /dev/ttyUSB0 bulb-bk7231n-stock-full.bin
#   ...power-cycle the module when it says it's connecting.

# Option 2 — ltchiptool (reads the entire chip by default, auto-picks baud rate)
ltchiptool flash read bk7231n bulb-bk7231n-stock-full.bin -d /dev/ttyUSB0
```

Explicit-range form if you want to be certain:

```bash
bk7231tools read_flash -d /dev/ttyUSB0 -s 0x0 -l 0x200000 bulb-bk7231n-stock-full.bin
```

### Verify the dump size — this is the standard failure

```bash
stat -c%s bulb-bk7231n-stock-full.bin
```

> **It must be exactly `2097152` bytes (2 MiB).** The bk7231tools docs are explicit:
> *"A valid dump for a standard 2M BK7231 should be 2,097,152 bytes. If your dump is any other size,
> it is probably incomplete!"* Anything else ⇒ re-read. Do not proceed on a short dump.

**Read it twice and compare** (same reasoning as A.4):

```bash
bk7231tools read_flash -d /dev/ttyUSB0 bulb-bk7231n-stock-verify.bin
cmp bulb-bk7231n-stock-full.bin bulb-bk7231n-stock-verify.bin \
  && echo "BACKUP GOOD" || echo "MISMATCH — DO NOT PROCEED"
sha256sum bulb-bk7231n-stock-*.bin | tee backups.sha256
```

Leave `--no-verify-checksum` **off**. It defaults to off, checksums are verified, and that's what you
want. (Since bk7231tools v1.0.0 the flag is no longer needed even on BK7231N — older guides telling
you to pass it are stale.)

## B.5 Extract keys and config from the dump (do this while you still can)

```bash
cd ~/sengled-backups

# Inventory the RBL containers in the dump (read-only, prints info)
bk7231tools dissect_dump bulb-bk7231n-stock-full.bin

# Extract app payloads + the encrypted Tuya key-value storage
bk7231tools dissect_dump -e --storage -O stock_extract bulb-bk7231n-stock-full.bin

# Also keep the raw RBL containers (useful for a byte-exact restore)
bk7231tools dissect_dump -e --rbl -O stock_extract_rbl bulb-bk7231n-stock-full.bin

ls -R stock_extract
```

Flags verified against the local `bk7231tools dissect_dump --help`:
`-e/--extract`, `--rbl` (keep the container, not just the payload), `--storage` (extract raw storage
values into separate files), `-O/--output-dir`, `-l/--layout` (default `ota_1`).

The `--storage` output is where the **Tuya device UUID, authkey, PSK, and the GPIO/dp configuration**
live. The GPIO config is directly useful: it tells you which pins drive which LED channel and which
LED driver IC is fitted, so you don't have to guess your OpenBeken/ESPHome pin map.

> On BK7231N, Tuya's storage is commonly encrypted with the well-known static key
> `510fb093 a3cbeadc 5993a17e c7adeb03`; bk7231tools knows it and applies it automatically when
> PyCryptodome is present. This is why the `[cli]` extra matters.

**Copy the backups and extracts off this machine now.**

## B.6 Get the new firmware

### Option 1 — OpenBeken (OpenBK7231T_App) — recommended first target

Download the **QIO** build for your chip from
<https://github.com/openshwprojects/OpenBK7231T_App/releases>:

```bash
cd ~/sengled
# For BK7231N (CB3S / CBLC5 / CB2S / CBU / WB2L_M1):
curl -fLO https://github.com/openshwprojects/OpenBK7231T_App/releases/latest/download/OpenBK7231N_QIO.bin
# For BK7231T (WB3S / WBLC5 / WB2S):
#   grab OpenBK7231T_QIO.bin instead
```

> **`QIO` vs `UA` vs `UG`:**
> - **`_QIO_`** = **full image including the bootloader** → flash at **`0x0`**. This is what you want
>   over UART.
> - **`_UA_`** / **`_UG_`** = app-only OTA images (no bootloader) → would go at **`0x11000`**.
>   Not what you want for a wired flash.
>
> **You do not need to compute this.** `ltchiptool flash write` auto-detects the file type and
> chooses family, start address, skip, and length automatically — this is the single biggest reason
> to prefer it over the legacy `hid_download_py` / `bkWriter` route, where getting `--startaddr`
> wrong is a known bricking path.

### Option 2 — ESPHome via LibreTiny

LibreTiny support is built into modern ESPHome (verified: `esphome/components/bk72xx/` and
`esphome/components/libretiny/` are present in the installed 2026.7.4).

```yaml
esphome:
  name: bulb-br30-01
  friendly_name: BR30 Bulb 01

bk72xx:
  board: cblc5           # or: cb3s, cb2s, cbu, generic-bk7231n-qfn32-tuya
                         # BK7231T parts: wblc5, wb3s, wb2s, generic-bk7231t-qfn32-tuya

logger:
api:
  encryption:
    key: !secret api_key
ota:
  - platform: esphome
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap: {}
captive_portal:

# Example RGBCW via a BP5758D constant-current driver (very common in these bulbs).
# CBLC5 exposes PWM0=P6, PWM4=P24, PWM5=P26 — P24/P26 are the usual BP5758D data/clock pair.
# Confirm against the GPIO config you extracted in B.5 before trusting this.
```

**Verified board names** (from the installed `esphome/components/bk72xx/boards.py`): `cblc5`, `cb3s`,
`cb2s`, `cb3se`, `cbu`, `generic-bk7231n-qfn32`, `generic-bk7231n-qfn32-tuya`, `wb3s`, `wblc5`,
`xh-wb3s`. `cblc5` is registered with `family: FAMILY_BK7231N` — that's the RGBCW bulb module.

> ⚠️ **Pick the right board.** ltchiptool bakes the board/family into the UF2 and the LibreTiny docs
> warn to pay *"careful attention to correct board selection to avoid bricking."* On a BK7231N that's
> recoverable; on a BK7231T it may not be.

Build and locate the artifact:

```bash
esphome compile bulb.yaml
ls -l .esphome/build/bulb-br30-01/.pioenvs/bulb-br30-01/firmware.uf2
```

> ### 🔧 CORRECTION TO THE BRIEF
> For LibreTiny/Beken targets ESPHome emits a **`firmware.uf2`**, not a `.bin`. Verified against the
> installed source: `esphome/components/libretiny/__init__.py` declares
> `{"file": "firmware.uf2", "download": f"{storage_json.name}.uf2"}`. The `.bin`
> (`image_bk7231x_app.ota.ug.bin`) exists too but is the **OTA/tuya-cloudcutter** artifact, not the
> wired-flash one. **Flash the `.uf2` with ltchiptool.**

## B.7 Write the firmware

```bash
cd ~/sengled

# Sanity-check what ltchiptool thinks the file is — do this BEFORE writing.
ltchiptool flash file OpenBK7231N_QIO.bin
```

It should report the family (`beken-7231n`) and the target offset. If it reports the wrong family,
**stop** — you have the wrong binary.

```bash
# Write OpenBeken (auto-detected family / address / length)
ltchiptool flash write OpenBK7231N_QIO.bin -d /dev/ttyUSB0
#   ...power-cycle the module as soon as it starts connecting.

# — or — write the ESPHome UF2
ltchiptool flash write .esphome/build/bulb-br30-01/.pioenvs/bulb-br30-01/firmware.uf2 \
  -d /dev/ttyUSB0
```

If auto-detection can't identify the file (custom/unrecognized build), you must supply **both**
family and start — verified from `ltchiptool flash write --help`: *"specifying only `-s/--start` is
not possible and requires `-f/--family` as well."*

```bash
ltchiptool flash write firmware.bin -d /dev/ttyUSB0 -f bk7231n -s 0x0
```

### Baud rates for BK7231N

- **Link/handshake baud is `115200`** — hardcoded. Verified in the source:
  `ltchiptool/soc/bk72xx/flash.py` calls `self.conn.fill_baudrate(115200)`, and
  `bk7231tools/serial/main.py` defaults `link_baudrate: int = 115200`. **The initial handshake always
  happens at 115200 regardless of what you ask for.**
- **After linking, the tool issues a `BkSetBaudRateCmnd` and switches to the transfer baud.**
  `ltchiptool` picks this automatically (`-b` default is *"auto choose, depending on the chip
  capabilities"*). **Just let it choose.**
- If you want to override: `-b 921600` is the practical fast option, `-b 460800` a safer middle
  ground, `-b 115200` the always-works fallback.
- **Symptoms of too-high baud:** checksum errors, mid-transfer aborts, "Timed out". **Drop to
  `-b 115200` and retry before suspecting anything else.** With short wires and a solid 3.3 V supply,
  921600 is usually fine; with 30 cm of tacked-on wire it is not.

```bash
# Conservative write if the fast path is flaky
ltchiptool flash write OpenBK7231N_QIO.bin -d /dev/ttyUSB0 -b 115200 -t 30
```

Leave the `-c/--check` hash/CRC verification **on** (it's the default). Don't pass `-C`.

### The legacy route (for reference only — prefer ltchiptool)

The old OpenBeken FLASHING.md documents `hid_download_py`/`uartprogram` with
`--unprotect -w --startaddr 0x0` for the N-variant QIO binary. **This is the error-prone path** —
`--startaddr` must be `0x0` for QIO-with-bootloader and `0x11000` for app-only, and getting it wrong
bricks things. ltchiptool derives it from the file. Use ltchiptool.

Equivalent with bk7231tools, if you ever need byte-level control:

```bash
# App-only image, no bootloader (NOTE: -s 0x11000). Do NOT pass -B on a BK7231T.
bk7231tools write_flash -d /dev/ttyUSB0 -s 0x11000 dump_app.bin
```

## B.8 First boot

1. **Power-cycle the module** once the write reports success.
2. **OpenBeken** raises an open AP named `OpenBK7231N_XXXXXX`. Join it, browse to
   **`http://192.168.4.1`**, and configure WiFi.
3. Then set the LED driver in **Config → Configure Module**. Common bulb drivers and their OpenBeken
   settings:
   - **BP5758D** → data/clock typically **P24 / P26**
   - **SM2235** → OBK default `SM2235_Current 2 4` (RGB, CW)
   - **SM2135** → similar 2-wire config
   - Plain 5-channel PWM → assign `PWM` roles to the five channel pins
   Use the GPIO config you extracted in **B.5** to get this right first try, or check the OpenBeken
   device database at <https://openbekeniot.github.io/webapp/devicesList.html> for your exact bulb.
4. **ESPHome-LibreTiny** joins your WiFi from the compiled-in credentials, or raises its fallback AP.
5. **Disconnect the adapter completely — power and data — before reassembling and applying mains.**

## B.9 If it turns out to be Realtek or LN882H

If `chip_info` / `flash info` reports **RTL8710BN/BX**, **RTL8720CF/CM**, or **LN882HK**, you're
still in the right toolchain — LibreTiny/ltchiptool covers all of them. Substitute the family:

```bash
ltchiptool list families               # authoritative list, run locally
ltchiptool flash read realtek-ambz  dump.bin -d /dev/ttyUSB0    # RTL8710B
ltchiptool flash read realtek-ambz2 dump.bin -d /dev/ttyUSB0    # RTL8720C
ltchiptool flash read lightning-ln882h dump.bin -d /dev/ttyUSB0 # LN882H
```

ESPHome's `rtl87xx:` platform is the LibreTiny equivalent of `bk72xx:`.

## B.10 Restoring stock

```bash
# BK7231N only. On BK7231T this overwrites the bootloader and is a one-way trip.
ltchiptool flash write ~/sengled-backups/bulb-bk7231n-stock-full.bin \
  -d /dev/ttyUSB0 -f bk7231n -s 0x0
```

Restoring a full-flash dump on a **BK7231T** requires writing the bootloader region and is
genuinely risky. Prefer restoring only the app region with `bk7231tools write_flash -s 0x11000`
using the payload you extracted in B.5.

---

# SECTION 3 — QUICK REFERENCE

## Tools status on this machine

| Tool | Status | Install command |
|---|---|---|
| `esptool` **5.3.1** | ✅ **installed** (pipx) | `pipx install esptool` |
| `esphome` **2026.7.4** | ✅ **installed** (pipx) | `pipx install esphome` |
| **`ltchiptool`** | ❌ **NOT installed** | **`pipx install ltchiptool`** (add `[gui]` for the GUI) |
| **`bk7231tools`** | ❌ **NOT installed** | **`pipx install "bk7231tools[cli]"`** ← `[cli]` extra required for key extraction |
| `dialout` group | ✅ JP is a member | — |
| `ch341`/`cp210x`/`ftdi_sio`/`pl2303` | ✅ all present | — |

(`ltchiptool 4.14.4` and `bk7231tools` were installed into a throwaway venv at `a throwaway venv`
purely to verify their CLI surface; that venv can be deleted. They are **not** on the PATH.)

## Command cheat-sheet

```bash
# ── ESP (Procedure A) ─────────────────────────────────────────────
esptool -p /dev/ttyUSB0 chip-id                                   # identify
esptool -p /dev/ttyUSB0 flash-id                                  # flash size
esptool -p /dev/ttyUSB0 read-flash 0x0 0x100000 stock.bin         # BACKUP (1MB)
esptool -p /dev/ttyUSB0 erase-flash                               # erase
esptool -p /dev/ttyUSB0 write-flash -fm dout -fs 1MB 0x0 fw.bin   # write
esptool -p /dev/ttyUSB0 verify-flash -fm dout -fs 1MB 0x0 fw.bin  # verify
# GPIO0 → GND at power-up.  Re-enter download mode before EACH command.

# ── Beken (Procedure B) ───────────────────────────────────────────
bk7231tools chip_info  -d /dev/ttyUSB0                            # identify N vs T
bk7231tools read_flash -d /dev/ttyUSB0 stock.bin                  # BACKUP (2MB)
bk7231tools dissect_dump -e --storage -O extract stock.bin        # extract keys
ltchiptool flash file OpenBK7231N_QIO.bin                         # sanity-check file
ltchiptool flash write OpenBK7231N_QIO.bin -d /dev/ttyUSB0        # write
# START THE COMMAND FIRST, then power-cycle the module.
```

## Failure → cause table

| Symptom | Most likely cause |
|---|---|
| ESP: `Timed out waiting for packet header` | GPIO0 not low at reset; or TX/RX swapped; or brownout |
| ESP: flashes OK, never boots, on an **ESP8285** | Used `-fm qio`/`dio` instead of **`-fm dout`** |
| ESP: only garbage on the console | Wrong baud — ESP ROM boot log is **74880**, app is 115200 |
| Beken: `Timed out attempting to link with chip` | Didn't power-cycle *after* starting the command; or TX/RX swapped |
| Beken: links, then checksum errors mid-transfer | Baud too high (`-b 115200`) or an inadequate 3.3 V supply |
| Either: works for reads, fails on long writes | **Power.** Adapter's 3V3 can't sustain the write burst — use an external supply |
| Dump is not exactly 1 048 576 / 2 097 152 bytes | Incomplete read — **re-read, do not proceed** |
| Two dumps differ | Unstable link or marginal power — **do not trust either backup** |
| Beken: module dead after a write, was a `WB*` part | It was a **BK7231T** and the bootloader got clobbered. See B.0. |

## Corrections to the original brief (summary)

1. **`WB3S` is BK7231T, not BK7231N.** Only `CB3S` is BK7231N. Confirmed via the Tuya CB3S datasheet
   and LibreTiny's board database. This distinction determines whether the part is brickable.
2. **ESPHome does not produce a `factory.bin` for ESP8266/ESP8285** — that artifact is ESP32-only.
   ESP8266/ESP8285 → **`firmware.bin`** @ `0x0`. Confirmed in the installed ESPHome 2026.7.4 source.
3. **ESPHome-LibreTiny produces `firmware.uf2`**, not a `.bin`, for the wired-flash path.
4. **For a *bulb*, the likely modules are the lighting variants** — `CBLC5` (BK7231N), `WBLC5`
   (BK7231T), or `TYLC5` (ESP8285, **1 MB** flash) — not the generic `*3S` parts the brief listed.
5. **esptool v5 uses hyphenated commands** (`read-flash`, not `read_flash`). Most tutorials online,
   including Tasmota's own esptool page, still show the v4 underscore syntax.

---

## Sources

- [esptool v5 Migration Guide — Espressif](https://docs.espressif.com/projects/esptool/en/latest/esp32/migration-guide.html)
- [esptool Basic Commands](https://docs.espressif.com/projects/esptool/en/latest/esp32/esptool/basic-commands.html)
- [esptool ESP8266 Troubleshooting (power requirements)](https://docs.espressif.com/projects/esptool/en/latest/esp8266/troubleshooting.html)
- [Tasmota — Esptool](https://tasmota.github.io/docs/Esptool/)
- [Tasmota — TYWE3S](https://tasmota.github.io/docs/devices/TYWE3S/)
- [Tuya TYLC5 Module Datasheet](https://developer.tuya.com/en/docs/iot/wifilc5module?id=K9605t3bpxf75)
- [Tuya CB3S Module Datasheet](https://developer.tuya.com/en/docs/iot/cb3s?id=Kai94mec0s076)
- [LibreTiny — Beken BK72xx platform](https://docs.libretiny.eu/docs/platform/beken-72xx/)
- [LibreTiny — ltchiptool manual](https://docs.libretiny.eu/docs/flashing/tools/ltchiptool/)
- [LibreTiny — Flashing ESPHome](https://docs.libretiny.eu/docs/flashing/esphome/)
- [ltchiptool on GitHub](https://github.com/libretiny-eu/ltchiptool)
- [bk7231tools README](https://github.com/tuya-cloudcutter/bk7231tools/blob/main/README.md)
- [OpenBK7231T_App — FLASHING.md](https://github.com/openshwprojects/OpenBK7231T_App/blob/main/FLASHING.md)
- [OpenBK7231T_App Releases](https://github.com/openshwprojects/OpenBK7231T_App/releases)
- [OpenBeken IoT device teardown database](https://openbekeniot.github.io/webapp/devicesList.html)
- [Blakadder Tasmota template repository](https://templates.blakadder.com/)
- Local verification: `esptool 5.3.1`, `ltchiptool 4.14.4`, `bk7231tools`, `esphome 2026.7.4`
  (`--help` output, `ltchiptool list boards/families`, `esphome/components/{esp8266,esp32,libretiny,bk72xx}` source,
  `bk7231tools/serial/{linking,protocol,main}.py`)
