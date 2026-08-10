# UART / Serial Flashing Procedure — WiFi RGBCW Smart Bulb (ASIN B097CYHRZJ)

**Status:** IN PROGRESS (started 2026-08-09 21:06 PDT)
**Sourcing:** compiled from FCC records, upstream project docs, and community tooling matrices.
**Target:** "FFS / Sengled" 7.5W BR30 RGBCW 2.4GHz WiFi bulb. WiFi module has `UART` silkscreened.
**Chip not yet confirmed** — two complete procedures below:
 - **Procedure A** — Espressif ESP8285 / ESP8266 → Tasmota / ESPHome
 - **Procedure B** — Beken BK7231N (WB3S / CB3S / WB2S modules) → OpenBeken / ESPHome-LibreTiny

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
  be at **full line potential** depending on which way the plug/socket is polarized.
- Your USB serial adapter's GND is bonded to your **PC's USB ground**, which is bonded (on a desktop)
  to **earth via the PSU**.
- Connecting the two while AC is applied puts **mains potential across your adapter, your USB port,
  your motherboard, and any peripheral you are touching.** The typical outcome is a destroyed adapter
  and PC; the atypical outcome is electrocution.

**The rules, in order:**

1. **UNPLUG the bulb from mains.** Remove it from the socket entirely. Do not "just switch it off at
   the wall" — a switched neutral leaves the board live.
2. **Wait ≥60 seconds** after unplugging before touching the board. The bulk electrolytic capacitor
   (usually a 6.8–22 µF / 400 V can) holds a lethal charge. **Verify with a DMM in DC volts across
   the bulk cap: it must read < 5 V** before you touch anything. If it holds charge, bleed it through
   a **10 kΩ / ≥2 W resistor** (not a screwdriver — that welds and shatters).
3. **Physically separate the LED/driver board from the RF module before flashing** where possible, or
   at minimum confirm no AC path exists. The safest posture: the driver board is **disconnected from
   any AC source and is only powered by your bench 3.3 V**.
4. **The module is powered ONLY from your 3.3 V source during flashing.** Never energize both the
   driver's AC input and the serial adapter at the same time. Not for "just a second."
5. **If you must observe the bulb running under mains** (e.g. capturing UART logs from a live device),
   you need a **mains isolation transformer** AND a **galvanically isolated USB-serial adapter**
   (opto/digital-isolated, e.g. an ADuM-based isolator). Do not improvise this. For flashing, you do
   not need it — just keep AC off.
6. **Never touch the board with one hand on a grounded object.** One-hand rule if AC has ever been
   near the bench.
7. **Do not power a non-isolated driver board from a bench supply's AC-side terminals.** If you want
   the LEDs to light for testing, use the 3.3 V rail for the module and drive the LEDs separately, or
   accept that you test light output only after reassembly with mains, adapter disconnected.

> **The one-line version: adapter ON ⇒ mains OFF. Mains ON ⇒ adapter OFF, module disconnected.
> The two states are mutually exclusive, forever.**

**Additional non-fatal-but-expensive rule:**

> ⚠️ **3.3 V LOGIC ONLY.** Both ESP8285 and BK7231N are **not 5 V tolerant**. If your USB-serial
> adapter has a 5 V/3.3 V jumper, set it to **3.3 V and verify with a meter on the TX pin before
> connecting.** A 5 V adapter will destroy the module. Many cheap CH340 boards ship jumpered to 5 V.

---

(working document — sections below appended as research proceeds)
