# Sengled "FFS" BR30 Color Bulb — Local Control Without the Cloud

Field notes for taking the **Sengled BR30 RGBCW WiFi bulb** (Amazon **ASIN B097CYHRZJ**,
listed as *"Updated FFS Smart Bulb … 65W Equivalent, 7.5W, Color Changing, 2.4GHz WiFi Only,
No Hub Required"*) **fully local** — no vendor cloud, no account, integrated into Home Assistant.

> ## ⚡ The short version
>
> **You almost certainly do not need to flash anything, and you do not need to solder anything.**
>
> Sengled's cloud collapsed in 2025, which is why your app is dead. But Sengled's own protocol has
> been reverse-engineered, so you can provision the bulb from a laptop over its own WiFi AP and
> drive it from Home Assistant over plain UDP on your LAN. **No cloud, no MQTT broker, no
> flashing, no teardown.** That is [Path 1](#path-1--solderless-local-control-recommended), and it
> works on *most or all* Sengled WiFi bulbs — **including the ones that cannot be flashed at all.**
>
> Flashing open firmware is still possible, but only on one of the two module variants — and it
> is now the *advanced* path, not the default.

**Status:** 🚧 Active research. Sections marked 🚧 are unconfirmed on this exact hardware.

---

## Contents

| | Section | |
|---|---|---|
| **0** | [Start here — the 5-minute ID check](#0-start-here--the-5-minute-id-check) | Decides which paths are open to you |
| **1** | [What this bulb actually is](#1-what-this-bulb-actually-is) | It's genuine Sengled, not Tuya |
| **2** | [Why the cloud is dead](#2-why-the-cloud-is-dead) | Context — not your fault |
| **3** | [**Path 1 — solderless local control**](#path-1--solderless-local-control-recommended) | ✅ **Recommended.** Any bulb. |
| **4** | [Path 2 — local MQTT server emulation](#path-2--local-mqtt-server-emulation) | Alternative to Path 1 |
| **5** | [Path 3 — solderless OTA to open firmware](#path-3--solderless-ota-to-open-firmware) | ESP8266 (WF863) only |
| **6** | [Path 4 — UART + LibreTiny](#path-4--uart--libretiny-experimental) | ⚠️ Experimental, zero prior art |
| **7** | [Ruled out: the Tuya exploits](#7-ruled-out-the-tuya-exploits) | Why they can't work here |
| **8** | [Home Assistant end state](#8-home-assistant-end-state) | Configs + what HA sees |
| **9** | [Credits & prior art](#9-credits--prior-art) | Everyone whose work this rests on |

---

## 0. Start here — the 5-minute ID check

Everything branches on **one marking**, and reading it requires **no teardown**.

### Read the FCC ID printed on the bulb's own plastic body

It reads `Contains FCC ID: 2AGN8-WF86x`. That single string decides everything:

| FCC ID | Module | Chip | Flashable? | Your paths |
|---|---|---|---|---|
| `2AGN8-WF863` | **WF863** | Espressif **ESP8266EX** | ✅ **yes, over the air** | 1, 2, **3** |
| `2AGN8-WF864` | **WF864** | MXCHIP **MX1290** (= Realtek RTL8710BN) | ❌ not with existing tools | 1, 2, ~~3~~, 4⚠️ |
| `2AGN8-WF862` | WF862 | MXCHIP MX1290 | ❌ | 1, 2, 4⚠️ |
| `P53-EMW3091` | EMW3091 | MXCHIP MX1290 | ❌ | 1, 2, 4⚠️ |

> ### ✅ Confirmed on the bulb behind these notes
> Module marking **`WF864SM-M6`**, **`FCC ID: 2AGN8-WF864`** → **MXCHIP MX1290 / Realtek
> RTL8710BN**. So for this ASIN: **no solderless flash path exists**, and
> [Path 1](#path-1--solderless-local-control-recommended) is the answer.
>
> **Read your own label anyway.** Sengled shipped multiple module generations concurrently, model
> numbers have been reused across revisions, and the flashable/not-flashable answer depends
> entirely on which one is in *your* hand. The good news: Path 1 works either way, so nothing
> blocks you while you look.

### If the label is worn: the antenna tells you at a glance

If you already have a module in front of you, you do not need a magnifier. The two modules have
**visibly different antennas**, and this is the fastest tell that exists:

```
  WF863  →  ESP8266  →  FLASHABLE            WF864  →  MX1290  →  not flashable
  ┌───────────────┐                          ┌───────────────┐
  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓ │ ← metal shield can       │ ▓▓▓[QR]▓▓▓▓▓▓ │ ← shield + QR sticker
  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓ │                          │ ▓▓▓▓▓▓▓▓▓▓▓▓▓ │
  └──┬─────┬──────┘                          └───────────────┘
     │ ███ │  ← WHITE CERAMIC BLOCK             ▐▐▐▐  ← plain GREEN etched
     └─────┘     overhanging the edge           ▐▐▐▐     trace, part of the PCB
   ╞═╡ 5 gold pads on a protruding tab        (pads along the board's own edge,
      (GND 3V3 RX TX IO0)                     no protruding tab)
```

> ### 🔑 The one-line tell
> **White ceramic antenna block → WF863 → ESP8266 → flashable.**
> **Plain green etched-trace antenna → WF864 → MX1290 → local control only.**

The module's solder side also prints it in plain text — `M/N: WF864` / `FCC ID: 2AGN8-WF864`.
Both descriptions above were verified against the FCC exhibit photographs on file for
[`2AGN8-WF863`](https://fccid.io/2AGN8-WF863) and [`2AGN8-WF864`](https://fccid.io/2AGN8-WF864).
*(The exhibits are not reproduced here — the test lab's report carries a
"not to be reproduced except in full" notice. Follow the links to view them at the source.)*

### About that "UART" silkscreen

If you have already opened a bulb and seen `UART` silkscreened near the module — **that does not
identify the chip.** The word `UART` appears on *none* of the WF862/WF863/WF864/WF867 FCC exhibit
photos; those modules label pins individually (`TX` `RX` `GND` `3V3`). It is most likely either
the **bulb's driver PCB** labelling the header where the module's serial pads land, or a later
production revision. It nudges slightly toward WF863 — whose serial pads sit on their own
protruding tab, exactly the kind of thing a vendor group-labels `UART` — but it does not settle
anything. **MX1290 is UART-programmable too** (ISP via UART2, pins `PA_29`/`PA_30`), so the label
implies nothing either way.

---

## 1. What this bulb actually is

### "FFS" is not a brand

The listing says *"Updated **FFS** Smart Bulb"*, and there is no "FFS" manufacturer to chase.
`FFS` is a fragment of **Sengled's own SKU**: Best Buy sells this exact product (SKU 6463039) as
*"Sengled Smart BR30 LED Bulbs Wi Fi … (2 Pack) Multicolor **W12-N15WFFS2P**"*. Decoding:
`W12-N15` (model) + `WF` (WiFi) + **`FS`** + `2P` (2-pack). The `WFFS` fragment is where the
Amazon title's "Updated FFS" comes from.

*(Plausibly `WFFS` itself encodes "WiFi + Frustration-Free Setup" — Amazon's zero-touch
provisioning, which these bulbs do support. Both readings land in the same place: **`FFS` is not a
third-party brand.**)*

### Model identity: Sengled **W12-N15**

| | |
|---|---|
| **Model** | `W12-N15` (BR30 multicolor) — from SKU `W12-N15WFFS2P` |
| **Expected module** | `WF864` = MXCHIP MX1290 = Realtek RTL8710BN |
| **Family** | `B097CYHRZJ` (2-pack) · `B097CYZWQ1` (4-pack) · `B097CZ49V8` (daylight sibling) |
| **Corroboration** | Sengled's form-factor digit convention: `E12-N14` = Zigbee **BR30**, `B12-N1E` = Bluetooth flood ⇒ `W12` = **WiFi BR30** |

⚠️ **Two honest caveats.** The `SengledTools` compatibility table labels `W12-N15` as *"WiFi white
LED"* while Best Buy sells it as *Multicolor* — most likely a description slip in the README, but
hardware revisions inside one model number are also possible. And one low-quality write-up
describes its W12-N15 bulbs as ESP8266-based, though that same article also writes "W15-N15" and
"W31-115", so its model strings are unreliable. **This is exactly why [§0](#0-start-here--the-5-minute-id-check)
tells you to read the FCC ID rather than trust any table.**

### Genuine Sengled, not a Tuya rebadge — *high confidence (~95%)*

- Sengled Co., Ltd. (Zhejiang Shenghui Lighting) holds its **own FCC grantee code `2AGN8`** —
  54 grants, 2016–2025 — covering a family of **self-designed WiFi modules**.
- Sengled ran its own cloud, its own *Sengled Home* app, its own OTA, and its own MQTT/UDP
  protocol. Not Smart Life, not Tuya.
- Field confirmation: the bulb broadcasts an open SoftAP named **`Sengled_Wi-Fi Bulb_XXXX`** —
  not a Tuya `SmartLife-XXXX` AP.
- **Ruled out with high confidence:** Beken BK7231T/BK7231N, Tuya WB3S/WB2S/CB3S/TYWE3S, and the
  entire Tuya platform.

> **Why the usual heuristic fails here.** *"Cheap RGBCW bulb in 2023+ ⇒ BK7231N"* describes
> white-label ODM bulbs built on Tuya's turnkey platform. Sengled is a real manufacturer with its
> own silicon choices. **Nothing in its WiFi line has ever been Beken or Tuya.**

### What the bulb's provisioning AP looks like

Observed on real hardware:

| | |
|---|---|
| SoftAP SSID | `Sengled_Wi-Fi Bulb_XXXX` (open, no password) |
| Bulb address | `192.168.8.1` on `192.168.8.0/24` *(the bulb's own factory AP subnet)* |
| Control protocol | **UDP port 9080** |
| Open TCP ports | **none** on 80, 8080, 8000, 5000, 9999, or 6668 |

That last row matters: **setup is not plain HTTP**, and port `6668` — the Tuya local-control port —
is closed, which is independent confirmation that this is not a Tuya device.

---

## 2. Why the cloud is dead

This is not a you-problem. The backend is gone.

| When | What |
|---|---|
| **2025-06-18 → 22** | Multi-day total cloud outage. WiFi bulbs dead across app, Alexa, and Google. No public statement from Sengled. |
| **2025-07-31** | Outage recurred; the app would not connect. |
| **2025-08-01** | Amazon **permanently discontinued the Sengled Alexa skill**, citing *"repeated extended service interruptions."* |
| Through 2025 | Sengled reportedly insolvent — staff unpaid since January, strikes by April. |

Sengled's **Zigbee and Matter** bulbs were unaffected, because they're controlled locally by a hub.
Only the WiFi line depended on the cloud — which is the line this bulb belongs to.

🚧 *A formal permanent-shutdown announcement could not be independently confirmed; treat "the cloud
is dead" as **probable but unverified**. It does not change anything below — every path here is
designed to not need it.*

---

## Path 1 — solderless local control ✅ recommended

**No flashing. No soldering. No teardown. No Sengled account. No MQTT broker.** Works on *most, if
not all* Sengled WiFi bulbs — explicitly **including modules that cannot be flashed**.

This is the path. Everything else in this document is either an alternative to it or an upgrade
from it.

### What you need

| | |
|---|---|
| **Software** | [`HamzaETTH/SengledTools`](https://github.com/HamzaETTH/SengledTools) — Python 3.10+ |
| **Hardware** | An ordinary laptop with **normal WiFi client mode** |
| **NOT needed** | ❌ AP-mode adapter ❌ monitor mode ❌ special chipset ❌ Docker ❌ Linux ❌ soldering iron |
| **Strongly recommended** | A **USB Ethernet adapter** — a second NIC lets you stay on your LAN while your WiFi is attached to the bulb's AP. This makes iteration dramatically less painful. |

### Step 1 — provision the bulb to your WiFi

```bash
git clone https://github.com/HamzaETTH/SengledTools.git
cd SengledTools
pip install -r requirements.txt

python sengled_tool.py --setup-wifi        # repeat once per bulb
```

1. **Factory-reset the bulb:** flick the power switch **5+ times** until it flashes.
2. The bulb broadcasts its own open AP, **`Sengled_Wi-Fi Bulb_XXXX`**. Your laptop joins it as an
   ordinary client — the bulb is at `192.168.8.1`, listening on **UDP 9080**.
3. The wizard pushes your WiFi credentials as an RC4-encrypted `setParamsRequest`.
4. The bulb then calls the tool's **local** server at `/jbalancer/new/bimqtt` and
   `/life2/device/accessCloud.json` — standing in for Sengled's dead cloud — and binds locally.

### Step 2 — control it from Home Assistant

Install the bundled **`sengled_udp`** custom integration. Bulbs appear as `light` entities driven
over **UDP 9080** on your LAN. Per its README: *"no cloud, no MQTT broker, and no flashing."*

### Practical friction to expect

The pairing flow was historically TLS-fragile — ALPN `x-amzn-mqtt-ca`, narrow TLS 1.2 cipher
selection, and a certificate SAN that breaks when the host IP changes. **PR #63 fixed all three.**

> ✅ **Two rules that save an evening:**
> 1. **Use current `master`**, not a release tarball.
> 2. **Give your host a static LAN IP** so the cert SAN stays valid.

### Why this is trustworthy for *this* model

`SengledTools` **PR #63** (merged ~Jun 2026) was tested on *"W12-N15 bulbs on stock firmware"* and
fixed exactly the out-of-box-activation / credentials-don't-persist failure. **That is this
model.** It is the single most decisive datum in this whole document: the recommended path is not
theoretical here — it is the path someone already debugged on this bulb.

### ⚠️ Avoid the older cloud-proxy integrations

`jfarmer08/ha-sengledapi`, `ripleyeldridge/...`, and `kylev/ha-sengledng` all proxy the **Sengled
cloud API**, which no longer exists. Only post-shutdown designs (`sengled_udp`,
`ha-sengled-local`) can work, because only they assume the cloud is gone.

---

## Path 2 — local MQTT server emulation

A heavier alternative to Path 1: run a **full local replacement for Sengled's cloud** and let stock
bulbs connect to it as if nothing had changed.

- [`FalconFour/ha-sengled-local`](https://github.com/FalconFour/ha-sengled-local) — HA integration
  + add-on. *"Brings your Sengled smart bulbs back to life after Sengled shut down their cloud
  servers."* Supports **all** WiFi ("No Hub Required") Sengled bulbs.
- Pairing is still done by **SengledTools**, pointed at the add-on's `/bimqtt` and
  `accessCloud.json` URLs instead of Sengled's.

**Choose Path 1 unless you specifically want MQTT.** Path 2 needs an add-on plus a Mosquitto
broker; Path 1 needs neither. Path 2's advantage is that it speaks the bulb's native MQTT dialect,
so if your bulb misbehaves on UDP it's the natural fallback.

---

## Path 3 — solderless OTA to open firmware

> **Requires `2AGN8-WF863` / ESP8266EX.** On WF864/MX1290 this simply does not work — the tool
> refuses, and there is nothing to fall back on but [Path 4](#path-4--uart--libretiny-experimental).

Here is the part most guides get wrong: **on ESP8266 units, flashing open firmware is *also*
solderless.** `SengledTools` impersonates Sengled's own cloud and pushes an arbitrary image over
WiFi — Sengled's OTA mechanism *is* exploitable, it just isn't Tuya's.

```bash
# 1. Provision as in Path 1, then push the rescue shim over the air
python sengled_tool.py --mac <BULB_MAC> --upgrade "firmware/shim.bin"
```

2. The bulb reboots into **`Sengled-Rescue`**, its own AP. Join it and open
   **`http://192.168.4.1`** — it is slow, keep refreshing.
3. **Back up the full flash first** (*full → backup selected*). This is your only way home.
4. Then flash **Tasmota / ESPHome / WLED** (*boot → choose `.bin` → flash selected*).

**Known gotchas:**

- *"write blocked (overlaps running slot)"* → some bulbs boot `ota_0` instead of `ota_1`. Use the
  Rescue UI's **"Relocate to ota_1"**, reboot, retry.
- Expect **several attempts**, power-cycling between tries. This is documented as flaky
  (SengledTools issues #47, #48).
- ⚠️ *"Flashing firmware carries risk of permanently bricking your bulb."*

**If your bulb is WF863, this is a genuinely good outcome:** every bulb can be converted to ESPHome
with zero disassembly, and you end up owning the firmware outright.

### 🛑 `--force-flash` on a non-ESP8266 module: **do not**

This is the single most dangerous thing you can do with these tools, and it is one flag away from
the happy path. **It is not an "advanced option." It is a brick.**

The tool gates flashing behind a **two-entry allowlist** — `{"W31-N11", "W31-N15"}` — and
`--force-flash` overrides that gate. On a WF864 that means **pushing an Xtensa binary at an ARM
core.**

> **Why the built-in safety net will not save you:** the shim's own guard —
> *"Not ESP8266 image slated for boot, avoiding brick"* — **executes inside the shim**. The shim is
> an ESP8266 binary. On an MX1290 it never runs at all, so the one check that would have stopped you
> is the very thing that can't execute. **The guard only ever protects an ESP8266.**

If the allowlist blocks your bulb, that is the tool correctly telling you your module is not
supported. Use [Path 1](#path-1--solderless-local-control-recommended).

---

## Path 4 — UART + LibreTiny ⚠️ experimental

> **This is speculative R&D, not a procedure. There is zero prior art. You would be first.**

If your module is **WF864 / MX1290** and you still want open firmware, this is the only *currently
available* route — and it is a poor trade against Path 1, which already gives you full local control
for free.

### 💡 The better unlock: an MX1290 shim binary

Before you reach for a soldering iron, understand where the wall actually is. **Sengled's OTA
transport is chip-agnostic** — it is Sengled's own updater, and it will happily deliver any payload
to any of these bulbs. Path 3 is not blocked by the transport. **It is blocked by the absence of an
MX1290/RTL8710BN build of the `Sengled-Rescue` shim.**

That reframes the whole problem:

- The missing piece is **one port of an existing shim to a second architecture** — a tractable
  software task someone will eventually do.
- It is a legitimate upstream feature request against
  [`HamzaETTH/SengledTools`](https://github.com/HamzaETTH/SengledTools), and it would unlock
  **solderless open firmware for this entire bulb family** at once.
- Not something to *wait* on — but a far better place to spend effort than eight mains-voltage
  teardowns.

If you have RTL8710BN experience, that port is the highest-leverage contribution available here.

**What makes it theoretically possible:**

- MXCHIP **MX1290 is a Realtek RTL8710BN** (ARM Cortex-M4F @ 125 MHz, 256 KB SRAM, 2 MB flash).
- RTL8710BN **is** supported by [LibreTiny](https://docs.libretiny.eu) as the `realtek-ambz`
  platform, and flashable with `ltchiptool`. So **ESPHome-over-LibreTiny is a real target.**
- One genuine comfort: on RTL8710BN **the UART bootloader lives in ROM**, so per LibreTiny it
  *"can't be software-bricked, even if you damage the bootloader."*

**What makes it a bad idea anyway:**

- **Zero prior art.** No published teardown of anyone flashing a Sengled WF864 bulb by any means.
- MX1290 is reported to ship *"potentially with flash encryption and log UART turned off."* If
  flash encryption is on, this ends here.
- No pin map exists. `UPK2ESPHome` — the tool that extracts GPIO mappings automatically — **only
  works on Tuya devices**, so pin discovery is fully manual ([§8](#8-home-assistant-end-state)).
- You'd be doing it **8 times**, with mains-voltage teardown each time, for a capability Path 1
  already gives you.

🚧 *Sources disagree here and I've resolved it toward the LibreTiny documentation: one research
note claimed no LibreTiny port exists for MX1290, but LibreTiny's own CPU list contains the entry
**"MX1290 (RTL8710BN)"**. The silicon is supported; the **device** is unexplored.*

### ⚠️ MAINS SAFETY — read this before opening any bulb ⚠️

> ### 🛑 THE BULB MUST BE UNPLUGGED FROM MAINS. ALWAYS. NO EXCEPTIONS.
> ### 🛑 NEVER connect a USB serial adapter to the bulb while the driver board is energized from AC.

**This is not boilerplate.** A smart bulb's driver is a **non-isolated (transformerless) switch-mode
power supply**. There is **no transformer and no optocoupler** between the AC line and the
low-voltage logic:

- The board's "GND" / 0 V node is **not earth**. It is typically tied to the **rectified mains
  negative rail**, which sits at up to **−170 V DC** (US 120 V AC peak) relative to neutral, and
  can be at **full line potential** depending on socket polarity.
- Your USB serial adapter's GND is bonded to your **PC's USB ground**, which on a desktop is bonded
  to **earth through the PSU**.
- Connecting the two while AC is applied puts **mains potential across your adapter, your USB port,
  your motherboard, and anything you are touching.** The typical outcome is a destroyed adapter and
  PC. The atypical outcome is electrocution.

**The rules, in order:**

1. **UNPLUG the bulb from mains.** Remove it from the socket entirely. Do not "just switch it off
   at the wall" — a switched-neutral fixture leaves the board live.
2. **Wait ≥ 60 seconds** after unplugging before touching the board. The bulk electrolytic
   capacitor (typically 6.8–22 µF / 400 V) holds a lethal charge. **Verify with a DMM in DC volts
   across the bulk cap: it must read < 5 V** before you touch anything. If it holds charge, bleed
   it through a **10 kΩ / ≥ 2 W resistor** — not a screwdriver, which welds and shatters.
3. **Physically separate the LED/driver board from the RF module before flashing** where possible,
   or at minimum confirm no AC path exists. Safest posture: the driver board is **disconnected from
   any AC source and powered only by your bench 3.3 V**.
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

**⚠️ 3.3 V LOGIC ONLY.** Both ESP8266/ESP8285 and RTL8710BN are **not 5 V tolerant**. If your
USB-serial adapter has a 5 V / 3.3 V jumper, set it to **3.3 V and verify with a meter on the TX
pin before connecting.** **Many cheap CH340 boards ship jumpered to 5 V** and will destroy the
module.

---

## 7. Ruled out: the Tuya exploits

Everyone tries these first. Here is precisely why neither can work — and note the reasoning is
**narrower than you might expect**.

### `tuya-cloudcutter` — disqualified by **vendor**, not by silicon

> **📝 Correction.** An earlier revision of this document claimed cloudcutter was disqualified on
> *both* silicon and vendor grounds. **The silicon half was wrong.** Cloudcutter's supported list
> includes **Realtek RTL8710BN** — which is exactly what MX1290 is. The disqualification is
> real, but it rests on **one** reason, not two.

- **The reason it fails: wrong vendor.** Cloudcutter attacks the **Tuya SDK's** cloud-activation
  handshake. Sengled firmware is Sengled's own — its own cloud, its own MQTT, its own app. There is
  no Tuya activation flow to impersonate. *Even where the chip is in scope, the firmware is not.*
- **It would be moot regardless.** RTL8710BN is only exploitable running **unpatched Tuya**
  firmware, and **Tuya patched the SDK in February 2022.**

<details>
<summary>Cloudcutter reference details, for when a genuinely Tuya device shows up</summary>

- **Supported chips:** BK7231T, BK7231N (unpatched), RTL8710BN (unpatched, SDK 2.0.0 excluded),
  RTL8720CF (caveats). **Not** ESP8266/ESP8285.
- **Known-patched BK7231N firmware:** 1.1.2, 1.1.12, 1.1.15, 1.3.3, 1.3.8, 1.3.10, 1.5.10, 2.0.15.
- **Host requirements:** Linux + NetworkManager + Docker + sudo, and a **secondary WiFi adapter
  whose driver supports AP mode via `nmcli`** (keep internet on Ethernet). No chipset allow-list is
  published; in practice mac80211-native drivers (`ath9k`, `ath9k_htc`, `mt76`, `rt2800usb`,
  `brcmfmac`) are the safe class, out-of-tree Realtek `rtl8812au`/`8821au` DKMS the flaky class.
- Requires a device **profile** to already exist for your exact device + firmware version.

</details>

### `tuya-convert` — deprecated *and* inapplicable

Patched by Tuya years ago; [`ct-Open-Source/tuya-convert`](https://github.com/ct-Open-Source/tuya-convert)
is archived and unmaintained. It only ever converted old unpatched **Tuya** stock. Moot here
regardless — not a Tuya device.

### Sengled's own OTA — *this one actually works*

Worth stating plainly, because it is the exception that makes [Path 3](#path-3--solderless-ota-to-open-firmware)
possible: **Sengled's OTA mechanism is exploitable.** `SengledTools` stands up a local MQTT broker
and HTTP server, impersonates the Sengled cloud, and pushes an arbitrary image. It is constrained
by **module** (ESP8266EX only) rather than by firmware version.

> **The corrected bottom line:** *"there is no wireless way to flash this bulb"* is **false**. On
> WF863 there is, and it's the recommended way. On WF864 there is no known way to flash it at all,
> wireless or wired — which is why [Path 1](#path-1--solderless-local-control-recommended) is the
> answer rather than a consolation prize.

---

## 8. Home Assistant end state

**Target:** each bulb appears as a single `light` entity with on/off, brightness, and color — and
**zero outbound internet traffic**.

### Path 1 / 2 end state

| | Path 1 (`sengled_udp`) | Path 2 (`ha-sengled-local`) |
|---|---|---|
| Transport | UDP 9080, direct to bulb | MQTT via local server |
| Extra services | none | add-on + Mosquitto |
| Firmware | stock | stock |
| Entities | `light.*` per bulb | `light.*` per bulb |

### Path 3 end state (ESPHome on ESP8266)

Recommended over Tasmota **specifically because there are 8 bulbs**: ESPHome's encrypted native API
needs no broker and auto-discovers, and `substitutions` + `packages` means **one canonical YAML plus
eight 3-line wrappers** instead of eight hand-configured web UIs.

⚠️ **Two corrections to the obvious approach:**

**It is probably 4-channel RGBW, not 5-channel RGBCW.** The only Sengled WiFi color bulb in the
Tasmota template DB is the W31-N15 — **4 channels, one white**. A bulb marketed as "color changing"
can fake color temperature by RGB mixing, so the marketing copy does *not* prove a 5th channel
exists. **Count the channels before writing the YAML.**

**It might not be direct PWM at all.** Many bulbs use a 2-wire (clock+data) constant-current LED
driver IC. A Hackaday teardown of a Sengled A19 found an **SM1533E** 3-channel driver — so Sengled
does ship driver ICs. *If you see a small 8-pin IC near the LED pads with only two traces back to
the module, the PWM config below is the wrong shape* — use `sm2135` / `bp5758d` / `bp1658cj` /
`my9231` instead.

```yaml
substitutions:
  device_name: bulb-br30-1
  friendly_name: "BR30 Bulb 1"

esphome:
  name: ${device_name}
  friendly_name: ${friendly_name}

esp8266:
  board: esp8285              # or esp01_1m
  restore_from_flash: true

logger:
  baud_rate: 0                # keeps the binary small — see the OTA trap below

api:
  encryption:
    key: !secret api_encryption_key
ota:
  - platform: esphome
    password: !secret ota_password

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    ssid: ${device_name}-ap   # a bulb that can't reach WiFi must STILL make light
captive_portal:

# Verified W31-N15 pinout — treat as the starting hypothesis, confirm per bulb
output:
  - { platform: esp8266_pwm, id: pwm_red,   pin: GPIO13, frequency: 1000 Hz }
  - { platform: esp8266_pwm, id: pwm_green, pin: GPIO12, frequency: 1000 Hz }
  - { platform: esp8266_pwm, id: pwm_blue,  pin: GPIO15, frequency: 1000 Hz }
  - { platform: esp8266_pwm, id: pwm_white, pin: GPIO14, frequency: 1000 Hz }

light:
  - platform: rgbw
    id: bulb
    name: None
    red: pwm_red
    green: pwm_green
    blue: pwm_blue
    white: pwm_white
    color_interlock: true       # RGB and white never on together — avoids muddy pastels
    restore_mode: ALWAYS_ON     # CRITICAL: wall switch on ⇒ light on
    default_transition_length: 400ms
```

> **`restore_mode: ALWAYS_ON` is the single most important line here.** ESPHome defaults to
> restoring the previous state — and a bulb that boots "off" when someone flips the wall switch
> reads as a *dead bulb* to the rest of the household.

<details>
<summary>Discovering the real pin map (if the W31-N15 mapping doesn't hold)</summary>

Flash a throwaway prober exposing every plausible GPIO as its own dimmable entity, then click each
one and write down which LED lights.

```yaml
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

Bring one up at a time at ~30% and note the color. **The channel count you find settles the
RGBW-vs-RGBCW question:** one white channel ⇒ `rgbw`; two whites of visibly different temperature
⇒ `rgbww`. **If no GPIO lights anything, that's the positive signal for a driver IC.**

</details>

> ### ⚠️ The 1 MB-flash OTA trap (verified — and it will bite)
> ESP8285 has 1 MB flash, and ESPHome OTA needs the *new* image to fit alongside the running one.
> Once a build exceeds roughly **~500 KB**, OTA fails with *"ESP does not have enough space to store
> OTA file"*. A `wifi` + `api` + `ota` + `light` config fits comfortably; people blow the budget by
> adding `web_server`, extra sensors, or `improv`. **Keep the config lean and keep
> `logger: baud_rate: 0`.** If you do exceed it, the escape hatch is to OTA a *minimal* config
> first, then OTA the full one — not disassembly.

### What HA shows you

- **Discovery** via mDNS; entities are `light.br30_bulb_1` … `_8`.
- **`rgbw`:** brightness + color wheel + white slider. `supported_color_modes: [rgbw]` — **no
  color-temperature slider**, because with one white LED there is no CT to tune.
- **`rgbww`:** adds a real color-temp slider bounded by your declared Kelvin values.
- **Device page** exposes an **Update entity** — new ESPHome builds appear as an HA update you push
  OTA from the UI.
- **Fully local:** encrypted native API over LAN; works with WAN down.

### Replicating across 8 bulbs

| Your module | Workflow |
|---|---|
| **WF863** | Convert **all 8 over the air** — no disassembly at all (Path 3). |
| **WF864** | Path 1 for all 8, ~5 minutes each, no hardware work. |

⚠️ **The "flash one by UART, then OTA the other seven" plan does not work** if you ever do need
wired flashing: OTA requires ESPHome to *already be running*, and with cloudcutter off the table
there is no wireless way to get the first image on. What OTA saves is **iteration**, not the first
flash. Nail the pin map once on the bulb that's already open, then flash the rest with the finished
config.

Per-bulb wrappers, once the shared config is proven:

```yaml
substitutions:
  device_name: bulb-br30-3
  friendly_name: "BR30 Bulb 3"
packages:
  common: !include common/sengled-br30.yaml
```

Your `secrets.yaml` (git-ignored) looks like:

```yaml
wifi_ssid: "YOUR_WIFI_SSID"
wifi_password: "YOUR_WIFI_PASSWORD"
```

---

## 9. Credits & prior art

None of this is my discovery. **Referenced by URL only — nothing is vendored here.**

### The projects that actually make this possible

| Project | Why it matters |
|---|---|
| **[`HamzaETTH/SengledTools`](https://github.com/HamzaETTH/SengledTools)** | The only serious prior art for these bulbs. Local WiFi onboarding, the `sengled_udp` HA integration, and the `Sengled-Rescue` flashing shim. **Path 1 and Path 3 are both this project's work.** |
| **[`FalconFour/ha-sengled-local`](https://github.com/FalconFour/ha-sengled-local)** | Local replacement Sengled MQTT server as an HA add-on + integration. Path 2. |
| [LibreTiny](https://docs.libretiny.eu) · [`ltchiptool`](https://github.com/libretiny-eu/ltchiptool) | Realtek `realtek-ambz` support — the only reason Path 4 is even theoretically on the map. |
| [`blakadder/templates`](https://github.com/blakadder/templates) | Tasmota template DB — source of the verified W31-N15 pinout. |
| [ESPHome](https://esphome.io) · [Tasmota](https://tasmota.github.io/docs/) · [Home Assistant](https://www.home-assistant.io) | The firmware and platform this all lands in. |

### Context projects (not applicable to Sengled, documented so you don't chase them)

[`tuya-cloudcutter`](https://github.com/tuya-cloudcutter/tuya-cloudcutter) ·
[`tuya-convert`](https://github.com/ct-Open-Source/tuya-convert) (archived) ·
[device DB](https://github.com/tuya-cloudcutter/tuya-cloudcutter.github.io) ·
[`bk7231tools`](https://github.com/tuya-cloudcutter/bk7231tools) ·
[`OpenBK7231T_App`](https://github.com/openshwprojects/OpenBK7231T_App)

*Note: **Tasmota has no BK7231 support at all** — LibreTiny ported ESPHome to Beken; nobody ported
Tasmota. OpenBeken describes itself as a "Tasmota/ESPHome replacement" precisely because Tasmota
doesn't run there. Irrelevant to this bulb, but it's a common misconception.*

### Research notes

Raw working notes with sourcing and confidence levels are in [`research/`](research/):

| File | Topic |
|---|---|
| [`01-chip-id.md`](research/01-chip-id.md) | Module ID from FCC exhibit photos, the antenna tell, model→module map |
| [`02-ota-path.md`](research/02-ota-path.md) | The no-solder verdict, SengledTools capability matrix, W12-N15 identification |
| [`03-uart-flash.md`](research/03-uart-flash.md) | Serial flashing procedures + full mains-safety treatment |
| [`04-ha-endstate.md`](research/04-ha-endstate.md) | Firmware choice per chip, ESPHome configs, HA end state |

---

## Disclaimer

Opening a mains-powered LED bulb exposes you to **lethal voltages**, destroys the bulb's thermal
design and any warranty, and may violate local electrical regulations. Flashing third-party
firmware can permanently brick the device. **You do this at your own risk.** The authors accept no
liability for damage, injury, or death.

**If you are not confident reading the mains-safety rules above and following every one of them,
use [Path 1](#path-1--solderless-local-control-recommended)** — it requires no teardown, no
soldering, and never exposes you to mains at all. For almost everyone, it is also simply the better
answer.

## License

[MIT](LICENSE) © JP ([@jphein](https://github.com/jphein))
