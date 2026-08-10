# UART Flashing — Sengled W12-N15 / WF864 (Realtek RTL8710BN)

**Status:** ✅ **ARMED — tooling installed, firmware staged, procedure ready to run**
(rewritten 21:40 PDT after chip confirmation; armed 23:05 PDT)
**Researcher:** Nebula
**Device:** Sengled W12-N15 BR30 RGB bulb (ASIN B097CYHRZJ), module **`WF864SM-M6` = MXCHIP MX1290 = Realtek RTL8710BN**, 2 MB flash

---

> # 🧪 STILL THE FALLBACK PATH — but it is now ready to execute on demand.
>
> **The adopted path remains Path A — `SengledTools` UDP local control.** No soldering, no flashing,
> no risk. See `the project state notes` and `research/02-ota-path.md`. As of this writing, provisioning is
> **shaky** (bulb accepts credentials but won't join), which is why this path has been armed.
>
> **Do not flash until Path A is formally declared dead.** JP has **8 bulbs**; Path A scales to all
> 8 in an evening. This path is roughly an hour for the *first* bulb, and there is **zero prior art
> for LibreTiny on the WF864 / MX1290** — nobody has published a success or a failure. You would be
> first.
>
> **What "armed" means:** `ltchiptool` is installed, a starter ESPHome config exists and compiles,
> and every command below is copy-pasteable. It does **not** mean the unknowns are resolved.
> **Read the Risk Register (Section 11) before touching a soldering iron** — the GPIO/driver-IC map
> is still unknown and is the one thing that can only be settled with hardware in hand.

---

## Table of contents

- **[SECTION A — READY TO RUN (the one-bulb procedure)](#section-a--ready-to-run)** ← start here
- [Section 0 — Mains safety (read first)](#section-0--mains-safety-read-this-first)
- [Section 1 — Chips ruled out: ESP8285 and BK7231 are NOT applicable](#section-1--ruled-out)
- [Section 2 — What makes RTL8710BN different](#section-2--what-makes-rtl8710bn-different)
- [Section 3 — Hardware you need (the adapter matters!)](#section-3--hardware-requirements)
- [Section 4 — Pads and wiring](#section-4--pads-and-wiring)
- [Section 5 — Entering download mode](#section-5--entering-download-mode)
- [Section 6 — Install the tools](#section-6--install-the-tools)
- [Section 7 — Probe: read chip info before anything else](#section-7--probe-first)
- [Section 8 — Back up the flash](#section-8--back-up-the-flash)
- [Section 9 — Build ESPHome for rtl87xx](#section-9--build-esphome-for-rtl87xx)
- [Section 10 — Write the firmware](#section-10--write-the-firmware)
- [Section 11 — Risk register & unknowns](#section-11--risk-register--unknowns)
- [Section 12 — Quick reference](#section-12--quick-reference)

---

# SECTION 0 — MAINS SAFETY. READ THIS FIRST.

> # 🛑 **THE BULB MUST BE UNPLUGGED FROM MAINS. ALWAYS. NO EXCEPTIONS.**
>
> # 🛑 **NEVER connect a USB serial adapter while the driver board is energized from AC.**

A smart bulb's driver is a **non-isolated (transformerless) SMPS**. There is **no transformer and no
optocoupler** between the AC line and the low-voltage logic. Therefore:

- The board's "GND" is **not earth**. It is tied to the **rectified mains negative rail** — up to
  **−170 V DC** relative to neutral on US 120 V, and potentially at **full line potential** depending
  on socket polarity.
- Your USB adapter's GND is bonded to **PC ground**, which on a desktop is bonded to **earth**.
- Connecting the two with AC applied puts **mains potential across your adapter, USB port,
  motherboard, and you.** Typical outcome: dead adapter and PC. Atypical outcome: electrocution.

**Rules, in order:**

1. **UNPLUG the bulb.** Remove it from the socket. A wall switch is not enough — switched-neutral
   fixtures leave the board live.
2. **Wait ≥60 s**, then **verify the bulk electrolytic cap reads < 5 V DC with a meter** before
   touching anything. If it holds charge, bleed it through a **10 kΩ / ≥2 W resistor** — never a
   screwdriver.
3. **The module is powered ONLY from your 3.3 V bench source during flashing.** Never energize AC and
   the adapter simultaneously. Not for one second.
4. **One-hand rule** whenever AC has been near the bench.
5. **Reassemble completely and disconnect the adapter — power AND data — before applying mains.**

> **One-line version: adapter ON ⇒ mains OFF. Mains ON ⇒ adapter OFF and physically disconnected.
> Mutually exclusive, forever.**

### ⚠️ 3.3 V logic only

RTL8710BN operates at **3.0–3.6 V** (verified: LibreTiny `realtek-ambz.json` → `"voltage": "3.0V - 3.6V"`).
It is **not 5 V tolerant.** If your adapter has a 5 V/3.3 V jumper, set it to 3.3 V **and measure the
TX pin** — some clones switch only the VCC rail and leave signals at 5 V.

---

# SECTION A — READY TO RUN

**The complete one-bulb procedure, start to finish.** Everything here is verified against installed
tooling. Sections 1–12 below are the reference material behind each step; you shouldn't need them
unless something deviates.

> **⛔ You have read Section 0 above. If you skipped it, go back.** The bulb must be unplugged, the
> bulk cap verified below 5 V, and the adapter must never be connected while AC is present.

## A.0 — Readiness checklist

| | Item | Status |
|---|---|---|
| ✅ | `ltchiptool` installed on the workstation | **v4.14.4** at `~/.local/bin/ltchiptool` (pipx) |
| ✅ | `realtek-ambz` family supported | confirmed via `ltchiptool list families` → *RTL8710B / 0x22E0D6FC / Supported: Yes* |
| ✅ | Board profile available | `generic-rtl8710bn-2mb-468k` (and `-788k`) in `ltchiptool list boards` |
| ✅ | `esphome` 2026.7.4 with `rtl87xx` | installed |
| ✅ | Starter firmware config staged | `ha-integration/esphome/sengled-br30-rtl8710bn.yaml` |
| ✅ | **Firmware actually builds** | `esphome compile` → **SUCCESS**, `firmware.uf2` produced (922 112 B) |
| ✅ | **UF2 validated by ltchiptool** | `ltchiptool flash file` → `UF2 - esphome 2026.7.4 (Type.VALID_UF2)` |
| ⚠️ | Flash headroom | **96.1 % full** (460 716 / 479 232 B) — only 18 516 B spare, see 11.5 |
| ✅ | `dialout` group membership | JP is a member |
| ✅ | USB-serial kernel drivers | `ftdi_sio`, `cp210x`, `ch341`, `pl2303` all present |
| ⚠️ | **USB-UART adapter capable of 1.5 Mbaud** | **VERIFY BEFORE STARTING — see A.1** |
| ⚠️ | Regulated 3.3 V supply ≥500 mA | Strongly recommended over the adapter's 3V3 pin |
| ❌ | **LED channel GPIO map** | **UNKNOWN — discovered on bulb #1, see A.8** |

## A.1 — ⚠️ CHECK YOUR ADAPTER FIRST (5 seconds, saves an evening)

The RTL8710B ROM handshake is **hardcoded at 1 500 000 baud** and cannot be lowered
(`AMBZ_ROM_BAUDRATE = 1500000`, verified in ltchiptool source).

> **LibreTiny, verbatim: "Some chips may not support 1.5M baud rate, required by the ROM for the
> initial handshake. Widespread PL2303 is currently known not to work... FT232RL is verified to work
> reliably."**
>
> **Use an FT232RL.** CP2102 is an acceptable second choice. **Do not start with a PL2303** — the
> failure is silent and looks exactly like a wiring fault. CH340 at 1.5 M is untested here.

Identify what you have once it's plugged in:

```bash
ls -l /dev/ttyUSB*
dmesg | tail -5                     # prints the driver: ftdi_sio / cp210x / ch341 / pl2303
```

**And set the adapter to 3.3 V, then measure its TX pin with a meter.** Some clones switch only the
VCC rail and leave signal lines at 5 V. RTL8710BN is 3.0–3.6 V and **not 5 V tolerant**.

## A.2 — Wiring

**Cross-over. GND first on, last off.** The flashing port is **UART2 (the LOG UART)**, not UART0.

```
  FT232RL @ 3.3 V                 WF864 module pads
  ───────────────                 ─────────────────
  GND       ─────────────────►    GND          ← connect FIRST, remove LAST
  RX        ◄─────────────────    TX    (PA30 / TX2 / Log_TX)
  TX        ─────────────────►    RX    (PA29 / RX2 / Log_RX)
  (unused)  ✗                     3V3   ◄───── external regulated 3.3 V, ≥500 mA
                                  BOOT  ─────── flying lead you can touch to GND
                                  ADC / TON     not used
```

### What is the `BOOT` pad? — determine it, don't assume (10 seconds)

RTL8710BN has **no dedicated BOOT pin**. The documented download strap is **PA30 = TX2 itself**, so
the `BOOT` pad is most likely a convenience breakout of PA30 placed so you can ground the strap
without shorting your adapter's RX line. **Meter it, board de-energized:**

| Test | Result | Meaning |
|---|---|---|
| `BOOT` ↔ `TX` continuity | **beeps** | `BOOT` is a PA30 breakout → **ground `BOOT`** in A.3 |
| `BOOT` ↔ `TX` continuity | no beep | `BOOT` is something else (likely CEN/reset) → **ground the `TX` pad directly** in A.3 |
| Ground `BOOT` briefly on a running module | module resets | it's **CEN** → use Method A in A.3 |

**Both outcomes have a working procedure.** Note whichever it is; you'll use it a dozen times.

## A.3 — Enter download mode

**The strap must be LOW at the instant reset releases, and released before the tool talks.**

### Method B (default — no CEN needed)

```
1. Module UNPOWERED (3V3 disconnected).
2. Connect the strap (BOOT, or the TX pad) → GND.
3. Apply 3.3 V.
4. Release the strap from GND.
```

### Method A (if `BOOT` turned out to be CEN)

```
1. Power applied.  2. CEN → GND.  3. TX2 → GND.  4. Release CEN.  5. Release TX2.
```

### ✅ CONFIRM IT WORKED — do not skip

```bash
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200
```

> **You should see a few garbage/grey-block characters printed once per second.** That's the ROM
> heartbeat. **Garbage = you are in download mode. Silence = you are not** — repeat A.3.
> (You will see nothing at all until the strap is released.)

Quit miniterm (`Ctrl-]`) before running ltchiptool — only one process can hold the port.

## A.4 — Probe (read-only, non-destructive)

```bash
ltchiptool flash info realtek-ambz -d /dev/ttyUSB0
```

Read three things off the output:

| Field | Expected | What it decides |
|---|---|---|
| `Chip Type` | `RTL8710BN` *(or `RTL8710BX` — fine, LibreTiny says firmware is interchangeable)* | confirms the family |
| `MAC Address` | starts `B0:CE:18` (Zhejiang Shenghui) | confirms it's the right board |
| **`OTA2 Address`** | **`0x00080000`** | **⭐ picks the board profile** |

> **`OTA2 Address` → board profile:**
> - `0x080000` → **`generic-rtl8710bn-2mb-468k`** ← expected (Realtek SDK default; this is not a Tuya device)
> - `0x0D0000` → `generic-rtl8710bn-2mb-788k` (Tuya default)
>
> The two boards have **byte-identical pin maps**; only partitioning differs. If it reads `0x0D0000`,
> change the `board:` line in the YAML before compiling.

## A.5 — ⚠️ RSIP ENCRYPTION PRE-CHECK — **the go/no-go gate**

**This is the one test that can kill the project, and it costs five minutes.** Do it before the
backup, before anything else.

RTL8710B's flash-encryption engine is **RSIP** (Realtek Secure Image Protection). Its configuration
lives in *system data* at flash offset **`0x9000`**, which is plain readable flash.

```bash
cd ~/sengled-backups 2>/dev/null || mkdir -p ~/sengled-backups && cd $_

ltchiptool flash read realtek-ambz syscfg.bin -d /dev/ttyUSB0 -s 0x9000 -l 0x1000
xxd -l 0x60 syscfg.bin
```

**Interpretation** (field offsets from `ltchiptool/soc/amb/system.py::SystemData`):

| Offset | Field | ✅ SAFE | ❌ STOP |
|---|---|---|---|
| `0x00`–`0x03` | `ota2_address` | any valid address | — |
| `0x10`–`0x17` | `rdp_address`, `rdp_length` | **all `FF`** | anything else = an RDP protected region exists |
| `0x50`–`0x57` | `rsip_mask1`, `rsip_mask2` | **all `FF`** | anything else = **flash encryption is ON** |

> ### 🟢 ALL `FF` AT `0x10` AND `0x50` ⇒ NOT ENCRYPTED ⇒ **SAFE TO PROCEED.**
>
> ### 🔴 ANYTHING ELSE ⇒ **STOP.** Do not flash.
> RSIP transparently decrypts flash during execute-in-place, so plaintext ESPHome written into an
> RSIP-covered region would decrypt into garbage and fail to boot — *even though the write reported
> success.* Capture `syscfg.bin` and the hexdump, report back, and reassess. Clearing the masks
> *may* be possible (they live in writable flash and ltchiptool already rewrites that sector to fix
> OTA2 addresses) — **but that is unproven inference, and you do not experiment on the only bulb
> you've opened.** Path A still exists.

Also capture the eFuse while you're here (hardware-level lock bits live there):

```bash
ltchiptool flash read realtek-ambz efuse.bin -d /dev/ttyUSB0 -E
```

*(`-E/--efuse` is supported on AmebaZ. `-R/--rom` is **not** — `can_read_rom=False` for this family.)*

## A.6 — Full-flash backup

**Mandatory.** The dump holds this bulb's **WiFi RF calibration** (partition `calibration` @
`0x00A000`) and its identity. Sengled's cloud is dead — **none of it is re-downloadable.**

```bash
cd ~/sengled-backups

# Re-enter download mode (A.3) first — each ltchiptool run needs a fresh entry.
ltchiptool flash read realtek-ambz sengled-w12n15-stock.bin -d /dev/ttyUSB0
```

### Verify: exact size, then read twice and compare

```bash
stat -c%s sengled-w12n15-stock.bin
```

> ### **Must be exactly `2097152` bytes (2 MiB). A short dump is a FAILED dump — re-read.**

```bash
# Re-enter download mode, then read a second copy
ltchiptool flash read realtek-ambz stock-verify.bin -d /dev/ttyUSB0

cmp sengled-w12n15-stock.bin stock-verify.bin \
  && echo "✅ BACKUP GOOD — proceed" \
  || echo "❌ MISMATCH — unstable link or weak 3.3V. DO NOT PROCEED."

sha256sum sengled-w12n15-stock.bin stock-verify.bin | tee backups.sha256
```

> **Two differing dumps means trust neither.** At 460 800 baud over tacked-on wire this is a real
> failure mode, and a corrupt backup you believe in is worse than no backup at all. Fix the power
> and the wires, then re-read.

Optional — split into named partitions for inspection:

```bash
ltchiptool flash split generic-rtl8710bn-2mb-468k sengled-w12n15-stock.bin
```

**Copy the backups off the workstation now.** Note: the `kvs` (`0x0F5000`) and `userdata` (`0x0FD000`)
partitions likely contain Sengled device tokens — **useful for the UDP work, and must never reach
the public repo.**

## A.7 — Build and flash

The starter config is already staged:

```
<your-workspace>/ha-integration/esphome/sengled-br30-rtl8710bn.yaml
<your-workspace>/ha-integration/esphome/secrets.yaml     (placeholders, .gitignore'd)
```

> ⚠️ **The 468k OTA slot is tight — 479 232 bytes, and the staged config only just fits.**
> This was found the hard way during staging: the first build overflowed `XIP1` by 15 840 bytes.
> `captive_portal` has been removed and `logger` set to `INFO` to make room. **Read the FLASH BUDGET
> block at the top of the YAML (and Section 11.5) before adding any component.**

Before compiling, put real values in `secrets.yaml` in that directory (it currently holds
placeholders and a throwaway API key, and is `.gitignore`d):

```bash
cd <your-workspace>/ha-integration/esphome
$EDITOR secrets.yaml        # wifi_ssid / wifi_password / ota_password
esphome compile sengled-br30-rtl8710bn.yaml
```

Artifact — **`.uf2`, not `.bin`**:

```bash
ls -l .esphome/build/sengled-br30-01/.pioenvs/sengled-br30-01/firmware.uf2
```

**Verified build output (2026-08-09 23:08 PDT, ESPHome 2026.7.4 + LibreTiny 1.13.0):**

```
RAM:   [=         ]  14.2% (used  37224 bytes from 262144 bytes)
Flash: [==========]  96.1% (used 460716 bytes from 479232 bytes)
========================= [SUCCESS] Took 57.76 seconds =========================

firmware.uf2                    922112 B   ← flash this
image_ota1.0x00B000.bin         460776 B
image_ota2.0x080000.bin         460776 B   ← note the 0x080000: confirms the 468k layout
```

> The `image_ota2.0x080000.bin` filename is independent confirmation of the OTA2-address mapping in
> A.4 — the 468k profile really does place OTA2 at `0x080000`. If the chip reports that address,
> this build matches it exactly.

> **Why UF2 matters:** `flash_write_uf2` reads system data at `0x9000`, decodes `ota2_switch` to
> determine **which OTA slot is currently active**, and writes to the correct one — automatically
> correcting the stored OTA2 address if it disagrees with the board profile. Flashing a raw
> `image_otaN.bin` to a guessed address is the documented way to get firmware that *"either [has] no
> effect ... or ... won't run."*

Sanity-check, then write:

```bash
ltchiptool flash file .esphome/build/sengled-br30-01/.pioenvs/sengled-br30-01/firmware.uf2
#   Already verified on the staged build — actual output was:
#     I: ...firmware.uf2: UF2 - esphome 2026.7.4 (Type.VALID_UF2)
#   Anything other than a VALID_UF2 line: STOP.

# Re-enter download mode (A.3), confirm the heartbeat, then:
ltchiptool flash write .esphome/build/sengled-br30-01/.pioenvs/sengled-br30-01/firmware.uf2 \
  -d /dev/ttyUSB0
```

Conservative retry if the transfer stage misbehaves:

```bash
ltchiptool flash write <path>/firmware.uf2 -d /dev/ttyUSB0 -b 115200 -t 30
```

> Link baud is fixed at **1 500 000**; the *transfer* baud defaults to **460 800** and is what `-b`
> changes. Lower the transfer rate on errors — you can never lower the link rate.

On success ltchiptool calls `ram_boot(0x00005405)` and the device starts the new firmware
immediately. **Remove the strap wire** so the next reset boots normally.

## A.8 — ❌ THE ONE UNKNOWN: find the LED channels

**There is no published GPIO map for the WF864/MX1290.** The staged YAML is therefore a **pin
prober** — it exposes every safe candidate pin as an independently dimmable light so you can find
the channels from HA Developer Tools.

**Strong hypothesis, test first.** RTL8710BN has exactly **5 hardware PWM channels**, and an RGBCW
bulb needs exactly 5 dimmable channels. On this board they map to:

| Channel | Pin | Safe to probe? |
|---|---|---|
| PWM1 | **PA15** | ✅ |
| PWM2 | **PA0** | ✅ |
| PWM3 | **PA12** | ✅ |
| PWM4 | **PA30** | ⚠️ this is the log UART TX / download strap |
| PWM5 | **PA22** | ✅ |

> **If exactly four channels light up, the fifth is almost certainly PA30** — which would also
> explain a vendor-disabled log UART, since you cannot have both PWM4 and serial logging. To test it,
> set `logger: baud_rate: 0` and uncomment the `pwm_pa30` block. **Flashing still works with logging
> off** — the download strap is a ROM-level function, independent of the app's logger.

> ### 🚫 PINS THAT MUST NEVER BE DRIVEN
> **PA6, PA7, PA8, PA9, PA10, PA11 are the SPI flash bus**
> (`SPI0_FCS=6, FD1=7, FD2=8, FD0=9, FSCK=10, FD3=11` — verified from ESPHome's board table).
> Driving any of them **will crash the chip and can corrupt flash.** They are deliberately excluded
> from the prober. Do not add them back.

Remaining safe GPIOs, already in the prober as fallbacks: `PA5`, `PA14`, `PA18`, `PA19`, `PA23`.

**If nothing lights up at all**, it isn't direct PWM — the bulb uses a constant-current driver IC
(**BP5758D / SM2135 / SM2235 / SM16716 / BP1658CJ**) on a 2-wire clock+data bus. **Look for such a
chip while the bulb is open** — checking during teardown is far cheaper than after reassembly. If
present, swap the prober for the matching ESPHome output platform and wire *clock* + *data*.

Once identified: fill in the FINAL CONFIG block at the bottom of the YAML, delete the prober, and
re-flash — **over OTA from that point on. No more soldering.**

## A.9 — Restore stock (if you change your mind)

```bash
ltchiptool flash write ~/sengled-backups/sengled-w12n15-stock.bin \
  -d /dev/ttyUSB0 -f realtek-ambz -s 0x0
```

A raw full-flash image isn't auto-detectable, so `-f` **and** `-s` are both required. This restores
the bootloader, RF calibration, and the original Sengled app.

## A.10 — Reassembly

1. **Remove the strap wire.**
2. **Disconnect the serial adapter completely — data AND power.**
3. Reassemble the bulb.
4. *Only then* apply mains.

---

# SECTION 1 — RULED OUT

The earlier drafts of this document contained full ESP8285 and BK7231N procedures. **Both are now
confirmed not applicable** and have been removed.

| Candidate | Verdict | Why |
|---|---|---|
| **ESP8285 / ESP8266** (`esptool`, Tasmota/ESPHome) | ❌ **NOT APPLICABLE** | Module is `WF864SM-M6` = MXCHIP MX1290 = **Realtek RTL8710BN** (ARM Cortex-M4F), not Espressif. `esptool` cannot talk to it at all. |
| **Beken BK7231N/T** (`ltchiptool`/`bk7231tools`, OpenBeken) | ❌ **NOT APPLICABLE** | Not a Beken part. OpenBeken has no RTL8710BN target in the `OpenBK7231T_App` release matrix that applies here, and `bk7231tools` is Beken-protocol-only. |
| **tuya-cloudcutter / tuya-convert** | ❌ **NOT APPLICABLE** | This is a **genuine Sengled** device, not Tuya-ecosystem (SoftAP `Sengled_Wi-Fi Bulb_XXXX`, MAC OUI `B0:CE:18` = Zhejiang Shenghui Lighting). No Tuya cloud handshake to exploit. |
| **Realtek RTL8710BN** (`ltchiptool` + LibreTiny `realtek-ambz`) | ✅ **THIS DOCUMENT** | Correct family. `ltchiptool` implements the AmebaZ ROM protocol. |

> One residual ambiguity worth resolving at probe time: the WF864 user manual lists **both**
> `MX1290` (133 MHz) and `MX1290V2` (62.5 MHz). LibreTiny documents RTL8710B**X** as *"the same chip
> but clocked at 62.5 MHz (instead of 125 MHz for BN)"* — so **`MX1290V2` is very likely an
> RTL8710BX, not BN.** Practically this is low-stakes: LibreTiny states *"firmware compiled for
> either of the chips can run on the other with no issues."* But `ltchiptool flash info` reports the
> real chip ID (Section 7) — check it rather than assuming.

---

# SECTION 2 — WHAT MAKES RTL8710BN DIFFERENT

If you have flashed ESP or Beken parts before, **unlearn three things.** These are the errors that
will cost you an evening.

### 2.1 The flashing port is the **LOG** UART (UART2), not UART0

LibreTiny: *"Realtek RTL8710B has two UART ports — UART2 (sometimes called LOG_UART) and UART0.
**The port used for flashing and viewing logs is UART2**."*

| Signal | Pin | Direction |
|---|---|---|
| **TX2 / Log_TX** | **PA30** | module → adapter RX |
| **RX2 / Log_RX** | **PA29** | adapter TX → module |

Independently confirmed in ESPHome's own pin table for `generic-rtl8710bn-2mb-468k`
(`esphome/components/rtl87xx/boards.py`): `"SERIAL2_RX": 29, "SERIAL2_TX": 30`.

### 2.2 The ROM handshake runs at **1.5 Mbaud** — and this eliminates most adapters

Verified in source (`ltchiptool/soc/ambz/util/ambztool.py`):

```python
AMBZ_ROM_BAUDRATE = 1500000
```

and in `ltchiptool/soc/ambz/flash.py`:

```python
# use 460800 max. as default, since most cheap adapters can't go faster anyway
self.conn.fill_baudrate(460800, link_baudrate=AMBZ_ROM_BAUDRATE)
```

So: **link at 1 500 000 baud, then negotiate down to 460 800 for the transfer.** You cannot lower the
link baud — it is fixed in the chip's mask ROM.

> ### 🚨 **THE SINGLE MOST IMPORTANT PRACTICAL FACT IN THIS DOCUMENT**
> LibreTiny, verbatim: *"You need a good USB↔UART adapter for the process. Some chips may not support
> 1.5M baud rate, required by the ROM for the initial handshake. **Widespread PL2303 is currently
> known not to work**, at least under Windows. **FT232RL is verified to work reliably.**"*
>
> **Use an FT232RL.** A CP2102 is a reasonable second choice (it clocks 1.5 M cleanly). **Do not
> start with a PL2303.** CH340 is unverified at 1.5 M for this application — plausible but untested.
> If your only adapter is a PL2303, buy an FT232RL before you begin; you will otherwise spend hours
> debugging a "wiring problem" that is an adapter problem.

`/dev/ttyACM0` is present on this machine (some other CDC device); your adapter will enumerate as
`/dev/ttyUSB0`. JP is already in `dialout`, and `ftdi_sio`, `cp210x`, `ch341`, `pl2303` modules are
all available.

### 2.3 Download mode is a **strapping pin held during reset**, and the strap is the **TX line itself**

There is no BOOT button and no polling handshake (unlike Beken). The ROM samples **PA30 (TX2)** at
reset; if it's low, it enters ISP/download mode. Realtek/MXCHIP documentation states this directly:
*"During the startup phase, if the processor hardware detects that the PA_30 level is low, it enters
the ISP programming mode. In ISP programming mode, you can program the flash of the module through
UART2 (PA_29, PA_30)."*

**This is counter-intuitive** — you ground the pin you're about to receive data on — and it is
exactly what confuses people. See Section 5, including a documentation contradiction I found and
resolved.

### 2.4 The good news: it is effectively unbrickable

LibreTiny: *"Because the UART uploading code is programmed in the ROM of the chip, it can't be
software-bricked, even if you damage the bootloader."*

The 512 KiB mask ROM always wins. If a write goes wrong, re-enter download mode and write again.
**This is the single biggest reason this path is worth attempting at all** — the failure mode is
"wasted evening", not "dead bulb". (Physical damage from soldering is a separate matter.)

---

# SECTION 3 — HARDWARE REQUIREMENTS

| Item | Requirement | Notes |
|---|---|---|
| **USB-UART adapter** | **FT232RL** strongly preferred | Must do **1.5 Mbaud**. **PL2303 known-broken.** Set to **3.3 V**. |
| **3.3 V supply** | Bench supply or 1117-type LDO, **≥500 mA** | See below — this is not optional advice |
| Wire | 30 AWG silicone, **< 15 cm** | Long leads + 1.5 Mbaud = failure |
| Power switch | A jumper or slide switch in the 3V3 line | You will power-cycle many times |
| DMM | Continuity + DC volts | For the cap check and pad identification |

> **On power:** ltchiptool's own built-in guide text says it twice —
> *"Using a good, stable 3.3V power supply is crucial. Most flashing issues are caused by either
> voltage drops during intensive flash operations, or bad/loose wires."* and *"The UART adapter's
> 3.3V power regulator is usually **not enough**. Instead, a regulated bench power supply, or a
> linear 1117-type regulator is recommended."*
>
> At 1.5 Mbaud with a Cortex-M4F at 125 MHz plus a WiFi PHY, a marginal rail produces symptoms that
> look exactly like protocol errors. **Power it properly from the start.** If you use an external
> supply: tie its GND to the adapter's GND, and **do not** also connect the adapter's 3V3 pin.

---

# SECTION 4 — PADS AND WIRING

### 4.1 What's on the WF864 module

Per the confirmed teardown (the project state notes), the module exposes: **`RX`, `TX`, `3V3`, `GND`, `BOOT`,
`ADC`, `TON`.**

Mapping to what you need:

| Module pad | Almost certainly | Use |
|---|---|---|
| `3V3` | VDD | Power in, 3.0–3.6 V |
| `GND` | GND | Common ground |
| `TX` | **PA30 / TX2 / Log_TX** | → adapter **RX**, **and** this is the download strap |
| `RX` | **PA29 / RX2 / Log_RX** | ← adapter **TX** |
| `BOOT` | ❓ **unverified** — see 4.2 | Possibly a breakout of PA30, possibly CEN |
| `ADC` | PA? analog in | Not needed |
| `TON` | vendor-specific ("touch on"?) | Not needed |

> ⚠️ **The `TX` and `RX` silkscreen is from the *module's* point of view** on virtually every Tuya /
> MXCHIP-style module — i.e. `TX` is the module's transmitter. **Cross them.** If in doubt, swap and
> retry; crossing is harmless for reads.

### 4.2 What is the `BOOT` pad? — **VERIFY THIS, DO NOT ASSUME**

The team brief described `BOOT` as "the RTL8710 download strap." That is a reasonable reading, but
**RTL8710BN has no dedicated BOOT pin** — the documented strap *is PA30/TX2*. So `BOOT` is most
likely **a convenience breakout of PA30**, placed so you can ground the strap without shorting your
adapter's RX line.

**Determine it with a meter in five seconds** (board de-energized):

```
DMM in continuity mode:
  BOOT pad ↔ TX pad     beeps  ⇒ BOOT is a PA30 breakout. Ground BOOT, leave TX wired to the adapter.
  BOOT pad ↔ TX pad   no beep  ⇒ BOOT is something else (likely CEN/reset, or a pull-up node).
                                 Fall back to grounding the TX pad directly (Section 5).
  BOOT pad ↔ 3V3        beeps  ⇒ it's pulled high — that's consistent with a strap input.
```

If `BOOT` turns out to be **CEN**, that's *also* useful — it gives you a clean reset without
power-cycling. Test: momentarily ground it on a running module; if the module resets, it's CEN.

**Either way you have a working procedure.** Section 5 covers both.

### 4.3 Wiring

```
  FT232RL (3.3 V)              WF864 module
  ───────────────              ────────────
  GND          ────────────►   GND        (connect FIRST, remove LAST)
  RX           ◄────────────   TX   (PA30 / Log_TX)
  TX           ────────────►   RX   (PA29 / Log_RX)
  (do not use) ✗               3V3  ◄──── external regulated 3.3 V, ≥500 mA
                               BOOT ────── flying lead to GND, for strapping
```

**In-place vs desoldered:** flash **in place**. The board is unplugged and the cap is discharged, so
the mains section is inert; desoldering the module risks lifting pads for no safety gain. Only
consider removing it if the driver circuitry actively fights the PA30 strap (unlikely — PA30 is a
UART pin, not an LED channel).

---

# SECTION 5 — ENTERING DOWNLOAD MODE

## 5.1 ⚠️ A documentation contradiction — resolved

LibreTiny's own sources disagree about which pin is the strap. I found this while reading the repo,
and it is a **known, still-open bug**: [libretiny#270, *"instructions contradictory in ltchiptool?"*](https://github.com/libretiny-eu/libretiny/issues/270),
opened 2024-04-01, **no maintainer resolution as of this writing.**

| Source | Says the strap is |
|---|---|
| `docs/platform/realtek-ambz/README.md` | **TX2 (PA30)** |
| `ltchiptool/soc/ambz/flash.py` → `AMEBAZ_GUIDE` step list | **TX2** |
| `boards/_base/realtek-ambz.json` → `doc.flashing.guide` step list | **PA30 (TX2)** |
| `boards/_base/realtek-ambz.json` → `doc.flashing.pins` dict | ⚠️ **PA29** ← the outlier |
| Realtek/MXCHIP ISP description | **PA_30** |

**Verdict: the strap is PA30 / TX2.** Four sources against one, and the one dissenter contradicts
the step list *inside its own file*. The `pins` dict entry is a typo.

*(The AMEBAZ_GUIDE prose is also awkwardly worded — "pulling CEN to GND briefly, while still keeping
the TX2 pin connected to GND" — which is what issue #270 is actually complaining about. The
**numbered step list is the correct operational sequence**; ignore the prose sentence.)*

## 5.2 The sequence

**Order matters. The strap must be low at the moment reset releases, and must be released before the
tool tries to talk.**

### Method A — you have CEN (or `BOOT` turned out to be CEN)

```
1. Wire up. Apply 3.3 V.
2. Connect CEN  → GND        (chip held in reset)
3. Connect TX2/BOOT → GND    (strap asserted)
4. Release CEN from GND      (chip boots, samples PA30 low → enters ISP mode)
5. Release TX2/BOOT from GND (frees the line for UART)
6. Verify (5.3), then run the ltchiptool command.
```

### Method B — no CEN pad (use power-cycling)

This is the officially sanctioned alternative — LibreTiny: *"if the CEN pin is inaccessible, toggle
3.3 V power instead (remove power = reset state; restore power = startup)."*

```
1. Wire up. Module UNPOWERED.
2. Connect TX2/BOOT → GND    (strap asserted)
3. Apply 3.3 V               (boots, samples PA30 low → ISP mode)
4. Release TX2/BOOT from GND
5. Verify (5.3), then run the ltchiptool command.
```

> **Note the ordering difference from Beken.** On BK7231 you start the tool *first* and then
> power-cycle. On RTL8710B it's the opposite: **get into download mode first, confirm it, then run
> the tool.** The chip stays in ISP mode indefinitely once entered.

## 5.3 Confirm you're in download mode BEFORE running anything

LibreTiny gives a distinctive tell:

> *"open a serial terminal ... You should see a few characters printed to the serial console every
> second (usually some kind of grey blocks, or other non-letter characters). Note that you will not
> see any characters before you release TX2 from GND."*

```bash
python3 -m serial.tools.miniterm /dev/ttyUSB0 1500000
```

**Once-per-second garbage bytes = you're in ISP mode. Proceed.** Silence = you are not; repeat 5.2.

*(The garbage is the ROM's heartbeat at 1.5 Mbaud being interpreted at whatever baud your terminal
is at — if you open at 115200 you'll see grey blocks, which is exactly what the docs describe.)*

---

# SECTION 6 — INSTALL THE TOOLS

> ### ✅ ALREADY DONE — `ltchiptool v4.14.4` is installed on the workstation (2026-08-09 23:03 PDT)
> ```
> $ ltchiptool --version
> ltchiptool v4.14.4
> $ which ltchiptool
> ~/.local/bin/ltchiptool
> ```
> Installed via `pipx install ltchiptool`. `realtek-ambz` confirmed supported
> (`RTL8710B / 0x22E0D6FC / Supported: Yes`) and both `generic-rtl8710bn-2mb-468k` and `-788k`
> board profiles are present.

For reference, on a fresh machine:

```bash
pipx install ltchiptool          # add [gui] if you want the GUI: pipx install "ltchiptool[gui]"
```

That's it — **`bk7231tools` is NOT needed** (Beken-only; ignore any earlier note saying otherwise).

Already present and sufficient:

```
esphome 2026.7.4   (pipx)   — has the rtl87xx / LibreTiny platform built in
```

Verified: `esphome/components/rtl87xx/` and `esphome/components/libretiny/` exist in the installed
2026.7.4, and `rtl87xx/boards.py` contains `generic-rtl8710bn-2mb-468k` and
`generic-rtl8710bn-2mb-788k`.

A local mirror of the source is already at `<your-workspace>/prior-art/ltchiptool/` and
`prior-art/libretiny/` — useful for reading protocol details offline (that's where most of this
document's verified facts came from).

> **The GUI is genuinely worth using for the first attempt.** `ltchiptool gui` shows the link
> handshake live, displays chip info in a panel, and removes a whole class of "did I type the family
> right" errors.

---

# SECTION 7 — PROBE FIRST

**Do this before backing up, and long before writing.** It answers three questions at once: is the
wiring right, which chip is it, and — critically — **which board profile to build for.**

```bash
ltchiptool flash info realtek-ambz -d /dev/ttyUSB0
```

Enter download mode (Section 5) first. Expected output fields (read directly from
`ltchiptool/soc/ambz/flash.py::flash_get_chip_info`):

```
Chip Type          RTL8710BN            ← 0xFF=BN, 0xF6=BX, 0xFE=BU, 0xFD=RTL8711BN
MAC Address        B0:CE:18:xx:xx:xx    ← should match the Sengled OUI ✓
Flash ID           XX XX 15             ← last byte 0x15 = 2 MB (size = 1 << id)
Flash Size (real)  2 MiB
OTA2 Address       0x00080000           ← ⭐ THIS PICKS YOUR BOARD — see below
SYSCFG 0/1/2       ...
ROM Version        Vx.y
CUT Version        X
```

### 7.1 ⭐ Use `OTA2 Address` to choose the board profile

This is the highest-value thing in this section, and it is not documented anywhere I could find — I
derived it from the board definitions plus `flash_write_uf2`'s behavior.

LibreTiny ships two 2 MB RTL8710BN layouts that differ **only** in partitioning (their pin maps are
byte-identical — I diffed the two board JSONs):

| Board | OTA1 | **OTA2** | App size | LibreTiny's own label |
|---|---|---|---|---|
| `generic-rtl8710bn-2mb-468k` | `0x00B000 + 0x75000` | **`0x080000`** | 479 232 B | *"**SDK default** for BN (2× 468k apps)"* |
| `generic-rtl8710bn-2mb-788k` | `0x00B000 + 0xC5000` | **`0x0D0000`** | 806 912 B | *"**Tuya default** for BN (2× 788k apps)"* |

**So:**
- `OTA2 Address` reads **`0x80000`** → use **`generic-rtl8710bn-2mb-468k`**
- `OTA2 Address` reads **`0xD0000`** → use **`generic-rtl8710bn-2mb-788k`**

**Prior expectation: `468k`.** This is a **Sengled/MXCHIP** device built on the stock Realtek SDK,
not a Tuya device — the "SDK default" layout is the natural fit, and it matches the team's
recommendation. **But read the actual value and let the chip decide.**

> If the value is neither, the vendor used a custom layout. `ltchiptool` handles this gracefully:
> `flash_write_uf2` compares the chip's `ota2_address` against the UF2's `ota2` partition offset and,
> if they differ, **rewrites system data at `0x9000` to correct it and forces OTA1**. (Verified in
> source.) It won't silently flash to the wrong place — but a mismatch does mean your board choice
> was wrong, so re-check rather than letting it "fix" things.

### 7.2 ⭐ Check for RSIP flash encryption

RTL8710B's flash encryption engine is **RSIP** (Realtek Secure Image Protection), configured by two
mask registers in *system data* at flash `0x9000`. `ltchiptool` models them
(`ltchiptool/soc/amb/system.py`):

```python
@dataclass
class RSIPMask:
    length: int
    offset: int
    is_disabled: bool
...
rsip_mask1: RSIPMask = bitfield("u7P2u22u1", RSIPMask, 0xFFFFFFFF)
rsip_mask2: RSIPMask = bitfield("u7P2u22u1", RSIPMask, 0xFFFFFFFF)
# plus an RDP (protected region) section:
rdp_address: int = field("I", default=0xFFFFFFFF)
rdp_length:  int = field("I", default=0xFFFFFFFF)
```

Default/unprogrammed = all `0xFF` = **disabled**. Dump and inspect:

```bash
# Read just the system-data sector
ltchiptool flash read realtek-ambz syscfg.bin -d /dev/ttyUSB0 -s 0x9000 -l 0x1000
xxd -l 0x60 syscfg.bin
```

Interpretation:
- Offsets `0x50`–`0x57` (rsip_mask1/2) all `FF` ⇒ **RSIP disabled — good, proceed.**
- Offsets `0x10`–`0x17` (rdp_address/length) all `FF` ⇒ **no RDP region — good.**
- Anything else ⇒ **STOP and read Section 11.1.**

Also dump the eFuse, which is where any hardware-level lock bits live:

```bash
ltchiptool flash read realtek-ambz efuse.bin -d /dev/ttyUSB0 -E
```

*(`-E/--efuse` is a supported read source for AmebaZ — verified in `flash_read_raw`. Note
`-R/--rom` is **not** supported here: `flash_get_features` returns `can_read_rom=False`.)*

---

# SECTION 8 — BACK UP THE FLASH

**Non-negotiable.** The dump contains this bulb's **per-device WiFi RF calibration** (partition
`calibration` @ `0x00A000`) and its **MAC/eFuse-derived identity**. These are unique to the unit and
**cannot be re-downloaded from anywhere** — Sengled's cloud is dead.

```bash
mkdir -p ~/sengled-backups && cd ~/sengled-backups

# Full 2 MB dump
ltchiptool flash read realtek-ambz sengled-w12n15-rtl8710bn-stock.bin -d /dev/ttyUSB0
```

`ltchiptool flash read` defaults to the entire chip from offset 0 and auto-selects the baud rate
(1.5 M link → 460 800 transfer). Add `-b 460800 -t 30` if you want to be explicit.

### Verify — and verify properly

```bash
stat -c%s sengled-w12n15-rtl8710bn-stock.bin      # MUST be exactly 2097152
```

> **A short dump is a failed dump. Do not proceed on one.**

**Read it twice and compare.** At 1.5 Mbaud over tacked-on wires this is not paranoia — a corrupt
backup you trust is worse than no backup:

```bash
ltchiptool flash read realtek-ambz stock-verify.bin -d /dev/ttyUSB0
cmp sengled-w12n15-rtl8710bn-stock.bin stock-verify.bin \
  && echo "BACKUP GOOD" || echo "MISMATCH — DO NOT PROCEED"
sha256sum *.bin | tee backups.sha256
```

Leave hash/CRC checking **on** — it's the default (`-c/--check`). Don't pass `-C`.

### Split the dump into named partitions (optional, useful)

```bash
ltchiptool flash split generic-rtl8710bn-2mb-468k sengled-w12n15-rtl8710bn-stock.bin
```

Known partition map for `realtek-ambz` (from `boards/_base/realtek-ambz.json` + the 468k layout):

| Partition | Offset + size | What it is |
|---|---|---|
| `boot_xip` | `0x000000 + 0x4000` | XiP bootloader |
| `boot_ram` | `0x004000 + 0x4000` | RAM bootloader |
| `system` | `0x009000 + 0x1000` | **System data — OTA2 addr, RSIP masks, RDP, flash mode/speed, log-UART baud** |
| `calibration` | `0x00A000 + 0x1000` | **⭐ RF calibration — irreplaceable** |
| `ota1` | `0x00B000 + 0x75000` | App slot 1 |
| `ota2` | `0x080000 + 0x75000` | App slot 2 |
| `kvs` | `0x0F5000 + 0x8000` | Key-value store (likely the WiFi creds / device token) |
| `userdata` | `0x0FD000 + 0x102000` | Vendor data |
| `rdp` | `0x1FF000 + 0x1000` | RDP region |

**Copy the backups off this machine before writing anything.** Also: the `kvs` and `userdata`
partitions may contain the **Sengled device token / cloud credentials** — potentially interesting for
extending the UDP protocol work in `research/02-ota-path.md`, and **definitely not publishable** to
the public repo (see the project state notes security rules).

---

# SECTION 9 — BUILD ESPHOME FOR rtl87xx

> ### ✅ Superseded by the staged config — use that, not the sketch below.
> **`<your-workspace>/ha-integration/esphome/sengled-br30-rtl8710bn.yaml`** is a complete,
> build-verified config with a pin prober. Section **A.7** is the live procedure. The sketch below is
> kept only to explain the platform keys; **it is not maintained and will drift.**

```yaml
# ── illustrative only — see the staged YAML ──
esphome:
  name: bulb-br30-01
  friendly_name: BR30 Bulb 01

rtl87xx:
  board: generic-rtl8710bn-2mb-468k     # ← confirm via OTA2 Address, Section 7.1

logger:
  # If the stock firmware disabled the log UART this is still fine —
  # LibreTiny reconfigures UART2 itself. See Section 11.2.

api:
  encryption:
    key: !secret api_key
ota:
  - platform: esphome
    password: !secret ota_password
wifi:
  ssid: !secret wifi_ssid          # YOUR_IOT_SSID / IoT your IoT VLAN — NEVER hardcode; see the project state notes
  password: !secret wifi_password
  ap: {}
captive_portal:

# ⚠️ LED channel pins are UNKNOWN — see Section 11.3.
# The WF864 datasheet lists 6 PWM channels. Determine the actual RGBCW mapping
# empirically before filling this in.
#
# output:
#   - { platform: libretiny_pwm, id: out_r, pin: P??, frequency: 1000 Hz }
#   ...
# light:
#   - platform: rgbww
#     ...
```

Build and locate the artifact:

```bash
cd <your-workspace>
esphome compile bulb-rtl.yaml
ls -l .esphome/build/bulb-br30-01/.pioenvs/bulb-br30-01/firmware.uf2
```

> **Flash the `.uf2`, not a `.bin`.** Verified in the installed ESPHome source
> (`components/libretiny/__init__.py` → `{"file": "firmware.uf2", ...}`) and in LibreTiny's
> realtek-ambz docs, which list the build outputs as:
>
> | File | Description |
> |---|---|
> | **`firmware.uf2`** | **UF2 package for UART and OTA upload** ← use this |
> | `image_ota1.0x00B000.bin` | OTA 1 image, flashable to `0xB000` |
> | `image_ota2.0x0D0000.bin` | OTA 2 image *(address varies by board)* |
>
> **Why UF2 matters here:** `flash_write_uf2` reads system data at `0x9000`, decodes
> `ota2_switch` (`ota_idx = 1 + (popcount_of_zero_bits % 2)`) to determine **which OTA slot is
> currently active**, and writes to the correct one. Flashing a raw `image_otaN.bin` to a guessed
> address is the documented way to end up with *"either no effect ... or upload firmware which won't
> run."* Let the UF2 path handle it.

---

# SECTION 10 — WRITE THE FIRMWARE

Sanity-check the file first — **always**:

```bash
ltchiptool flash file .esphome/build/bulb-br30-01/.pioenvs/bulb-br30-01/firmware.uf2
```

It should report family **`realtek-ambz`** and the target board. If it reports anything else, stop.

Re-enter download mode (Section 5), confirm the once-per-second garbage (5.3), then:

```bash
ltchiptool flash write .esphome/build/bulb-br30-01/.pioenvs/bulb-br30-01/firmware.uf2 \
  -d /dev/ttyUSB0
```

Conservative variant if the default 460 800 transfer rate misbehaves:

```bash
ltchiptool flash write firmware.uf2 -d /dev/ttyUSB0 -b 115200 -t 30
```

**Baud notes (verified in `ambztool.py`):** the link is always **1 500 000** and cannot be changed.
The *transfer* baud defaults to **460 800** and is selectable from a fixed table that includes
`115200, 230400, 460800, 500000, 921600, 1000000, 1500000, 2000000, …`. Lower the *transfer* rate on
errors; you can never lower the *link* rate.

After a successful write, `ltchiptool` issues `ram_boot(address=0x00005405)` — the device boots the
new firmware immediately without a power cycle.

## 10.1 First boot

1. **Remove the strap wire from GND.** (Leaving it grounded re-enters ISP mode on the next reset.)
2. Power-cycle.
3. Watch the log — LibreTiny's default log UART is the same UART2 you're already wired to:
   ```bash
   python3 -m serial.tools.miniterm /dev/ttyUSB0 115200
   ```
4. Join the fallback AP or watch for it on **your IoT VLAN (`YOUR_IOT_SSID`)**; HA reaches it from `YOUR_HA_IP`.
5. **Disconnect the adapter — power and data — before reassembling and applying mains.**

## 10.2 Restoring stock

```bash
ltchiptool flash write ~/sengled-backups/sengled-w12n15-rtl8710bn-stock.bin \
  -d /dev/ttyUSB0 -f realtek-ambz -s 0x0
```

A raw full-flash image isn't auto-detectable, so `-f` **and** `-s` are both required — verified in
`ltchiptool flash write --help`: *"specifying only `-s/--start` is not possible and requires
`-f/--family` as well."* This restores the bootloader, RF calibration, and the original app.

---

# SECTION 11 — RISK REGISTER & UNKNOWNS

**Honest accounting.** This is a first-of-its-kind attempt; here is what is actually known versus
assumed.

| # | Risk | Confidence | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **RSIP flash encryption enabled** | **Unknown** — one secondary source says MX1290 "potentially" ships with it | 🔴 High | **Check first (7.2).** If masks aren't `FF`, stop and reassess. |
| 2 | **Log UART disabled in stock firmware** | **Unknown**, same source | 🟡 Low | Doesn't block flashing — the ROM ISP path is independent (11.2). |
| 3 | **LED channel pin mapping unknown** | **Certain — it is unknown** | 🟡 Medium | Empirical discovery after flashing (11.3). |
| 4 | **`BOOT` pad function unverified** | **Unknown** | 🟢 Low | Meter test (4.2); TX-pad strap works regardless. |
| 5 | **PL2303 adapter can't do 1.5 Mbaud** | **Verified by LibreTiny** | 🔴 High if unaddressed | Use FT232RL. |
| 6 | **Wrong board layout (468k vs 788k)** | Resolvable | 🟡 Medium | Read `OTA2 Address` (7.1). |
| 7 | **Soldering damage / lifted pads** | Real | 🔴 High | Fine wire, strain relief, don't rework hot pads repeatedly. |
| 8 | **Software brick** | **Effectively impossible** | 🟢 None | ROM ISP always recoverable. |
| 9 | **App overflows the 468k OTA slot** | **CONFIRMED — hit it during staging** | 🟡 Medium | Config trimmed to fit; see 11.5 before adding components. |

### 11.5 ⚠️ Flash budget — confirmed tight (found while staging)

The 468k layout gives each OTA slot **479 232 bytes**, and that is not generous. The first build of
the staged config — with `captive_portal` and `logger: DEBUG` — **failed to link**:

```
ld: .pioenvs/sengled-br30-01/raw_firmware.ota1.elf section `.xip_image2.text' will not fit in region `XIP1'
ld: region `XIP1' overflowed by 15840 bytes
```

`captive_portal` was the main cost (it pulls in `web_server_base` + `DNSServer`). It has been removed
from the staged YAML, and `logger` dropped to `INFO`. **The trimmed build succeeds at 96.1 % full —
460 716 of 479 232 bytes, leaving just 18 516 bytes (3.9 %) of headroom.** RAM is fine at 14.2 %.

**Consequence:** no web setup form on the fallback AP. WiFi credentials are compiled in, so this only
bites if they're wrong — and on bulb #1 the UART wires are still attached, making a re-flash trivial.

**If you add components and overflow again, cut in this order:**
1. **`api: encryption:`** — libsodium + the Noise handshake is the single biggest block. Plaintext
   API is defensible on a segmented IoT VLAN.
2. `logger: level: NONE` or `baud_rate: 0`.
3. Fewer probe lights.
4. **Last resort:** switch to `generic-rtl8710bn-2mb-788k` (806 912 B/slot) — **but only if
   `ltchiptool flash info` actually reported `OTA2 Address = 0x0D0000`.** Forcing a layout the device
   doesn't use makes ltchiptool rewrite the partition table. It handles that correctly, but it isn't
   something to do casually on hardware with no prior art.

### 11.1 If RSIP *is* enabled

**This is the one that could stop the project.** RSIP transparently decrypts flash during XiP, so a
plaintext LibreTiny image written into an RSIP-covered region would decrypt into garbage and fail to
boot — *even though the write itself succeeded.*

**Reasoning, clearly labelled as inference — I found no prior art either way:**
- The RSIP masks live in **system data at `0x9000`**, which is plain flash and **is writable** by
  `ltchiptool` (it already rewrites this sector to fix OTA2 addresses).
- Therefore clearing/disabling the masks before flashing plaintext firmware is *probably* possible.
- **But** if the key is burned into eFuse and secure-boot bits are set, the bootloader may refuse
  unsigned images, and that is **not** software-reversible.

**If you find non-`FF` RSIP masks: stop, capture the dump and the syscfg hexdump, and reassess.**
Do not start clearing bits experimentally on the only bulb you've opened. Path A still works.

### 11.2 If the log UART is disabled

Not a blocker. The **ROM ISP path is in mask ROM** and does not depend on the application's logging
configuration — the app can only change `SystemData.baudrate` (the log-UART baud field at offset
`0x30`), and that field is read by the *bootloader/app*, not by the ROM's ISP handshake.

Consequences if disabled: (a) you won't see stock boot logs, and (b) Section 5.3's "garbage bytes"
check still works, because that heartbeat comes from ROM. **After flashing ESPHome, LibreTiny
configures UART2 itself and logging returns.**

### 11.3 Discovering the LED pin mapping

**Nobody has published this for the WF864.** The datasheet says 6 PWM channels; RGBCW needs 5.

Approach, in order of preference:

1. **Read it out of the stock firmware.** After Section 8, examine the `ota1` partition — a strings
   dump or a look at the GPIO init table can reveal the channel assignment. Cheapest option, zero
   risk, and you already have the dump.
2. **Trace the PCB.** Ohm out each module pin to the LED driver / MOSFET gates. Definitive but
   tedious.
3. **Brute-force after flashing.** Flash a minimal ESPHome config that exposes every plausible pin as
   an independent `libretiny_pwm` output, then toggle each from the HA dev-tools and watch which
   colour lights. Fastest in practice — **and safe, because it's unbrickable.**

Also check whether the bulb uses a **constant-current driver IC** (BP5758D / SM2135 / SM2235 —
2-wire clock+data) rather than direct PWM. If so, you need a completely different ESPHome output
platform. Look for such a chip on the board while you have it open — **do this during the teardown,
not after reassembly.**

### 11.4 The honest bottom line

**Estimated probability this path yields a working ESPHome bulb: moderate.** The chip family is
well-supported by LibreTiny and genuinely unbrickable, which is a strong foundation. The unknowns are
RSIP (potentially fatal, checkable in 5 minutes) and pin mapping (tedious but tractable).

**Do the Section 7 probe on one bulb before committing effort.** It costs one teardown and answers
the fatal question. If RSIP is clear and the pin mapping is discoverable, this is very likely to
work. **Keep the other 7 bulbs on Path A regardless** until bulb #1 is fully proven.

---

# SECTION 12 — QUICK REFERENCE

## Tools

| Tool | Status | Install |
|---|---|---|
| **`ltchiptool`** | ✅ **v4.14.4 INSTALLED** (pipx, `~/.local/bin/ltchiptool`) | `pipx install ltchiptool` |
| `esphome` 2026.7.4 | ✅ installed | — (rtl87xx platform built in) |
| **Starter YAML** | ✅ staged + compiles | `ha-integration/esphome/sengled-br30-rtl8710bn.yaml` |
| ~~`bk7231tools`~~ | not needed | Beken-only — **ignore earlier guidance** |
| ~~`esptool`~~ | installed but irrelevant | Espressif-only |
| FT232RL adapter | ⚠️ **verify you have one** | **PL2303 will not work** |
| **LED GPIO map** | ❌ **UNKNOWN** | Discover on bulb #1 — see A.8 |

## Commands

```bash
# 0. Enter download mode: strap TX2/BOOT → GND, reset (CEN or power-cycle), release strap.
#    Confirm: once-per-second garbage bytes on the serial terminal.

ltchiptool flash info realtek-ambz -d /dev/ttyUSB0                         # probe: chip, OTA2 addr
ltchiptool flash read realtek-ambz syscfg.bin -d /dev/ttyUSB0 -s 0x9000 -l 0x1000   # RSIP check
ltchiptool flash read realtek-ambz efuse.bin  -d /dev/ttyUSB0 -E           # eFuse
ltchiptool flash read realtek-ambz stock.bin  -d /dev/ttyUSB0              # BACKUP (2 MiB)
ltchiptool flash split generic-rtl8710bn-2mb-468k stock.bin                # partition split
ltchiptool flash file  firmware.uf2                                        # sanity-check
ltchiptool flash write firmware.uf2 -d /dev/ttyUSB0                        # WRITE
```

## Key numbers

| | |
|---|---|
| ROM link baud | **1 500 000** (fixed, in mask ROM) |
| Transfer baud | **460 800** default; lower on errors |
| Flash size | **2 MiB** = `2097152` bytes |
| Flashing UART | **UART2 / LOG_UART** — TX2 = **PA30**, RX2 = **PA29** |
| Download strap | **PA30 (TX2)** held low across reset |
| System data | flash `0x9000` — OTA2 addr, RSIP masks, RDP |
| RF calibration | flash `0x00A000` — **irreplaceable** |
| Board (expected) | `generic-rtl8710bn-2mb-468k` — confirm via `OTA2 Address = 0x80000` |
| ESPHome artifact | **`firmware.uf2`** |

## Failure → cause

| Symptom | Cause |
|---|---|
| No garbage bytes after the strap sequence | Strap not low at reset; or TX/RX swapped; or brownout |
| Link fails but wiring looks right | **PL2303 adapter can't do 1.5 Mbaud.** Use FT232RL. |
| Links, then errors mid-transfer | Transfer baud too high (`-b 115200`), long wires, or a weak 3.3 V rail |
| Dump ≠ 2 097 152 bytes | Incomplete read — re-read, do not proceed |
| Two dumps differ | Unstable link / marginal power — **trust neither backup** |
| Flash succeeds, device won't boot | Wrong board layout, **or RSIP encryption** (11.1) |
| Bulb lights the wrong colours | Pin mapping wrong — 11.3 |
| Device seems dead | It isn't. ROM ISP is always available — re-enter download mode. |

---

## What changed in this revision

Rewritten after the chip was confirmed as RTL8710BN. Removed the full ESP8285 and BK7231
procedures (now one-line "not applicable" rows in Section 1). Reframed as the experimental fallback
to Path A.

**Corrections carried forward from the previous revision** (chip identification is settled, but these
tooling facts still stand and appear in `01-chip-id.md` / `02-ota-path.md`):
- ESPHome emits **`firmware.uf2`** for LibreTiny targets, **`firmware.bin`** for ESP8266, and
  **`firmware.factory.bin`** only for ESP32.
- esptool v5 uses **hyphenated** subcommands.

**New findings in this revision:**
1. **The 1.5 Mbaud ROM handshake makes adapter choice decisive** — PL2303 is documented as
   non-working; FT232RL is the verified-good part. This is the likeliest cause of a wasted evening.
2. **A live documentation bug in LibreTiny** ([issue #270](https://github.com/libretiny-eu/libretiny/issues/270),
   open since 2024-04-01): `realtek-ambz.json`'s `pins` dict says the strap is **PA29** while its own
   `guide` steps, the platform README, ltchiptool's built-in guide, and Realtek's ISP description all
   say **PA30**. **PA30 is correct.**
3. **`OTA2 Address` from `flash info` deterministically selects the board profile** —
   `0x80000` → `468k`, `0xD0000` → `788k`. The two board definitions are otherwise byte-identical.
4. **RSIP flash encryption is checkable before committing** — the masks live in system data at
   `0x9000` and `ltchiptool` can read that sector directly. This converts the project's scariest
   unknown into a 5-minute test.
5. **`bk7231tools` is not needed at all** for this device — dropping it from the install list.

---

## Sources

**Local source verification** (`<your-workspace>/prior-art/`, offline mirrors):
- `ltchiptool/ltchiptool/soc/ambz/flash.py` — AMEBAZ_GUIDE, `fill_baudrate(460800, AMBZ_ROM_BAUDRATE)`, `flash_get_chip_info`, `flash_write_uf2` OTA-index logic, `can_read_rom=False`
- `ltchiptool/ltchiptool/soc/ambz/util/ambztool.py` — `AMBZ_ROM_BAUDRATE = 1500000`, `AMBZ_CHIP_TYPE`, `AMBZ_BAUDRATE_TABLE`
- `ltchiptool/ltchiptool/soc/amb/system.py` — `SystemData`: RSIP masks, RDP, flash mode/speed, log-UART baud
- `libretiny/docs/platform/realtek-ambz/README.md` — wiring, download mode, build outputs
- `libretiny/boards/generic-rtl8710bn-2mb-{468k,788k}.json` and `boards/_base/realtek-ambz*.json` — partition layouts, voltage, upload speed, the PA29/PA30 discrepancy
- Installed `esphome 2026.7.4` — `components/rtl87xx/boards.py` (`SERIAL2_RX: 29, SERIAL2_TX: 30`), `components/libretiny/__init__.py` (`firmware.uf2`)

**Web:**
- [LibreTiny — Realtek RTL8710BN/BX platform](https://docs.libretiny.eu/docs/platform/realtek-ambz/)
- [LibreTiny — Generic RTL8710BN (2M/468k) board](https://docs.libretiny.eu/boards/generic-rtl8710bn-2mb-468k/)
- [LibreTiny — ltchiptool manual](https://docs.libretiny.eu/docs/flashing/tools/ltchiptool/)
- [libretiny issue #270 — "instructions contradictory in ltchiptool?"](https://github.com/libretiny-eu/libretiny/issues/270)
- [ltchiptool on GitHub](https://github.com/libretiny-eu/ltchiptool)
- [FCC ID 2AGN8-WF864 — Sengled WiFi Module](https://fccid.io/2AGN8-WF864)
- [WF864 user manual (MX1290 / MX1290V2 specs)](https://manuals.plus/sengled/wf864-sengled-wifi-module-manual)
- [Realtek Ameba-Z datasheet v3.4 (archived)](https://web.archive.org/web/20211203124711if_/https://adelectronicsru.files.wordpress.com/2018/10/um0114-realtek-ameba-z-data-sheet-v3-4.pdf)
