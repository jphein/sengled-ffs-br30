# Sengled "FFS" BR30 Color Bulb — Local Control Without the Cloud

Taking the **Sengled BR30 RGB WiFi bulb** (Amazon **ASIN B097CYHRZJ**, sold as *"Updated FFS Smart
Bulb … 65W Equivalent, 7.5W, Color Changing, 2.4GHz WiFi Only, No Hub Required"*) **fully local** —
no vendor cloud, no account, no app, integrated into Home Assistant.

> ## ⚡ The short version
>
> **You do not need to flash anything. You do not need to solder anything.**
>
> Sengled's protocol has been reverse-engineered. You provision the bulb from a laptop over the
> bulb's own WiFi AP, then drive it from Home Assistant over plain **UDP on port 9080**. No cloud,
> no MQTT broker, no flashing, no teardown, ~5 minutes per bulb.
>
> That's **[Path 1](#path-1--solderless-local-control-recommended)**, and a working Home Assistant
> integration **already exists**. It's the recommended path for *every* Sengled WiFi bulb —
> including the ones that cannot be flashed at all, which (as it turns out)
> **[includes this one](#the-hardware-confirmed)**.

**Status:** Hardware identification is **complete and confirmed**. The Path 1 software exists and
is in use upstream; the extended feature set described in
[§4](#4-what-you-get-in-home-assistant) is written but 🚧 **not yet smoke-tested on hardware**.

---

## Contents

| | Section | |
|---|---|---|
| **0** | [Identify your module — 5 minutes, no teardown](#0-identify-your-module) | Decides which paths are open to you |
| **1** | [What this bulb actually is](#1-what-this-bulb-actually-is) | Confirmed hardware; genuine Sengled, not Tuya |
| **2** | [Why the vendor app doesn't work](#2-why-the-vendor-app-doesnt-work) | Context — not your fault |
| **3** | [**Path 1 — solderless local control**](#path-1--solderless-local-control-recommended) | ✅ **Recommended.** Any bulb, no hardware work. |
| **4** | [What you get in Home Assistant](#4-what-you-get-in-home-assistant) | Feature matrix + honest gaps |
| **5** | [Path 2 — local MQTT emulation](#path-2--local-mqtt-server-emulation) | Alternative to Path 1 |
| **6** | [Path 3 — solderless OTA flash](#path-3--solderless-ota-flash) | ESP8266 (WF863) only — **not this bulb** |
| **7** | [Path 4 — UART flash to open firmware](#path-4--uart-flash-to-open-firmware) | Wired, unexplored on this module, genuinely possible |
| **8** | [Ruled out: the Tuya exploits](#8-ruled-out-the-tuya-exploits) | Why they can't work here |
| **9** | [Credits & prior art](#9-credits--prior-art) | Everyone whose work this rests on |

---

## 0. Identify your module

Everything branches on **which radio module is inside**, and you can settle it **without opening
anything**.

### Easiest: read the FCC ID on the bulb's plastic body

It reads `Contains FCC ID: 2AGN8-WF86x`.

| FCC ID | Module | Chip | Solderless flash? | Wired flash? |
|---|---|---|---|---|
| `2AGN8-WF863` | WF863 | Espressif **ESP8266EX** | ✅ **yes** — [Path 3](#path-3--solderless-ota-flash) | ✅ yes |
| **`2AGN8-WF864`** | **WF864** | MXCHIP **MX1290** = Realtek **RTL8710BN** | ❌ no | ⚠️ [Path 4](#path-4--uart-flash-to-open-firmware) |
| `2AGN8-WF862` | WF862 | MXCHIP MX1290 | ❌ no | ⚠️ Path 4 |
| `P53-EMW3091` | EMW3091 | MXCHIP MX1290 | ❌ no | ⚠️ Path 4 |

**[Path 1](#path-1--solderless-local-control-recommended) works on every row**, so you can start
there regardless of what you find.

### Easier still: ask the bulb over the network

[`tools/probe_bulb.py`](tools/probe_bulb.py) reads the model straight out of the firmware over UDP
— no teardown, no pairing, no Home Assistant:

```bash
# Bulb in SoftAP mode (factory reset: flick power 5+ times), joined to its open AP:
./tools/probe_bulb.py                 # defaults to 192.168.8.1

# Or, if the bulb is already paired onto your LAN:
./tools/probe_bulb.py <bulb-ip>
```

It reports the model string (e.g. `…_W12-N15_SYSTEM_…`) and whether R/G/B channels are present.
`W31-N15` / `W31-N11` ⇒ WF863/ESP8266 ⇒ flashable. Anything else (`W12-*`, `W21-*`, `W11-*`) ⇒
MX1290 or EMW3091 ⇒ local control only.

### If you already have the module in your hand

Two independent visual tells, either of which settles it:

#### 1. The bootstrap pad — the sharpest discriminator

| Pad silkscreen | Meaning |
|---|---|
| **`IO0`** | ESP8266 bootstrap strap ⇒ **WF863 / ESP8266** |
| **`BOOT`** | RTL8710BN download strap ⇒ **WF864 / MX1290** |

They are *different chips' bootloader-entry pins*, so the label alone is decisive. This bulb's
module exposes **`RX` `TX` `3V3` `GND` `BOOT` `ADC`** — no `IO0`.

#### 2. The antenna — visible across the room

```
  WF863  →  ESP8266  →  flashable            WF864  →  MX1290  →  local control only
  ┌───────────────┐                          ┌───────────────┐
  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓ │ ← metal shield can       │ ▓▓▓[QR]▓▓▓▓▓▓ │ ← shield + QR sticker
  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓ │                          │ ▓▓▓▓▓▓▓▓▓▓▓▓▓ │
  └──┬─────┬──────┘                          └───────────────┘
     │ ███ │  ← WHITE CERAMIC BLOCK             ▐▐▐▐  ← plain GREEN etched
     └─────┘     overhanging the edge           ▐▐▐▐     trace, part of the PCB
   ╞═╡ 5 gold pads on a protruding tab       (pads along the board's own edge,
      (GND 3V3 RX TX IO0)                     no protruding tab)
```

> ### 🔑 One-line tells
> **`IO0` pad, or white ceramic antenna block → WF863 → ESP8266 → flashable.**
> **`BOOT` pad, or plain green etched-trace antenna → WF864 → MX1290 → local control only.**

Both descriptions were verified against the FCC exhibit photographs on file for
[`2AGN8-WF863`](https://fccid.io/2AGN8-WF863) and [`2AGN8-WF864`](https://fccid.io/2AGN8-WF864).
*(The exhibits are linked rather than reproduced here — the test lab's report carries a "not to be
reproduced except in full" notice.)*

### About the "UART" silkscreen

If you've opened a bulb and seen `UART` silkscreened near the module, **that does not identify the
chip.** The word appears on none of the WF862/WF863/WF864/WF867 FCC exhibit photos — those label
pins individually. It's most likely the bulb's *driver PCB* labelling the header where the module's
serial pads land. Use `BOOT`-vs-`IO0` instead; that one is decisive.

---

## 1. What this bulb actually is

### The hardware (confirmed)

Identified three independent ways — the module silkscreen, the FCC grant, and the network
behaviour:

| | |
|---|---|
| **Bulb model** | Sengled **W12-N15** — BR30 multicolor RGB, E26, 7.5 W, 2.4 GHz WiFi only |
| **Module** | **`WF864SM-M6`** |
| **Chip** | **MXCHIP MX1290** = **Realtek RTL8710BN** (ARM Cortex-M4F, 2 MB flash) |
| **FCC / IC** | `2AGN8-WF864` / `20888-WF864` |
| **Board** | `LLPC35560_V1`, dated 2020-12-02 |
| **UART pads** | `RX` `TX` `3V3` `GND` **`BOOT`** `ADC` |
| **Verdict** | ❌ **Not OTA-flashable.** ⚠️ Wired UART flashing is possible but unexplored — see [Path 4](#path-4--uart-flash-to-open-firmware). |

> ### ⚠️ "Not OTA-flashable" ≠ "not flashable"
> This distinction matters and is easy to get wrong (an earlier revision of this document did).
> The **wireless** flash path is closed because the only Sengled OTA flasher pushes an ESP8266
> (Xtensa) shim and this is an ARM core. But MX1290 is a **Realtek RTL8710BN rebadge**, which sits
> squarely inside mature open-firmware tooling. **Wired flashing is a real, supported target.**

### "FFS" is not a brand

`FFS` = **Amazon Frustration-Free Setup** (Wi-Fi Simple Setup — zero-touch provisioning against an
Echo already on your network). It's a *feature*, and Sengled encoded it into its own SKU:
`W12-N15`**`WFFS`**`2P` — `W12-N15` + `WF` (WiFi) + `FS` (Frustration-free Setup) + `2P` (2-pack).
Best Buy sells this exact product under that SKU. Either way: **there is no "FFS" manufacturer to
chase.**

### Genuine Sengled, not a Tuya rebadge

Confirmed three ways, which matters because it's what rules out every popular flashing exploit:

| Evidence | What it shows |
|---|---|
| **FCC grantee code `2AGN8`** | Sengled Co., Ltd. (Zhejiang Shenghui Lighting) — 54 grants, 2016–2025, its own self-designed modules |
| **SoftAP name `Sengled_Wi-Fi Bulb_XXXX`** | Not a Tuya `SmartLife-XXXX` AP |
| **MAC OUI `B0:CE:18`** | IEEE assignment to Zhejiang Shenghui Lighting = Sengled |
| **TCP port `6668` closed** | That's Tuya's local-control port. Nothing is listening. |

Sengled ran its own cloud, its own app, its own OTA, and its own MQTT/UDP protocol — **not** Smart
Life, not Tuya. **Ruled out with high confidence:** Beken BK7231T/N, Tuya
WB3S/WB2S/CB3S/TYWE3S, and the entire Tuya platform.

> **Why the usual heuristic fails here.** *"Cheap RGBCW bulb in 2023+ ⇒ BK7231N"* describes
> white-label ODM bulbs built on Tuya's turnkey platform. Sengled is a real manufacturer with its
> own silicon choices. **Nothing in its WiFi line has ever been Beken or Tuya.**

### The bulb's provisioning AP

| | |
|---|---|
| SoftAP SSID | `Sengled_Wi-Fi Bulb_XXXX` (open, no password) |
| Bulb address | `192.168.8.1` *(the bulb's own factory AP subnet)* |
| Control protocol | **UDP port 9080**, plain unauthenticated JSON |
| Open TCP ports | **none** — setup is not HTTP |

---

## 2. Why the vendor app doesn't work

This is not a you-problem, and it is not a misconfiguration.

| When | What (documented) |
|---|---|
| **2025-06-18 → 22** | Multi-day cloud outage. WiFi bulbs unresponsive via app, Alexa, and Google. |
| **2025-07-31** | Outage recurred; the app would not connect. |
| **2025-08-01** | Amazon **discontinued the Sengled Alexa skill**, citing *"repeated extended service interruptions."* |

**Sengled's cloud has suffered repeated prolonged outages since mid-2025 and the vendor app is
unreliable.** That is the sourced, documented claim, and it's all this project needs — every path
below is designed to not depend on the cloud at all.

Sengled's **Zigbee and Matter** bulbs were unaffected, because a local hub controls them. Only the
WiFi line depended on the cloud, and that's the line this bulb is in.

---

## Path 1 — solderless local control ✅ recommended

**No flashing. No soldering. No teardown. No Sengled account. No app. No MQTT broker.**

Works on *most, if not all* Sengled WiFi bulbs — explicitly **including modules that cannot be
flashed**, which is why it's the answer for this bulb rather than a consolation prize.

### What you need

| | |
|---|---|
| **Software** | [`HamzaETTH/SengledTools`](https://github.com/HamzaETTH/SengledTools) — Python 3.10+ |
| **Hardware** | An ordinary laptop with **normal WiFi client mode** |
| **NOT needed** | ❌ AP-mode adapter ❌ monitor mode ❌ special chipset ❌ Docker ❌ Linux ❌ soldering iron |
| **Recommended** | A **USB Ethernet adapter** — a second NIC lets you stay on your LAN while your WiFi is attached to the bulb's AP. Makes iteration far less painful. |

### Step 1 — provision the bulb onto your WiFi

```bash
git clone https://github.com/HamzaETTH/SengledTools.git
cd SengledTools
pip install -r requirements.txt

python sengled_tool.py --setup-wifi        # interactive; repeat once per bulb
```

1. **Factory-reset the bulb:** flick the power switch **5+ times** until it flashes.
2. The bulb broadcasts its own open AP, **`Sengled_Wi-Fi Bulb_XXXX`**. Your laptop joins it as an
   ordinary client — the bulb is at `192.168.8.1` on **UDP 9080**.
3. The wizard pushes your WiFi credentials as an RC4-encrypted `setParamsRequest`.
4. The bulb then calls the tool's **local** server at `/jbalancer/new/bimqtt` and
   `/life2/device/accessCloud.json` — standing in for Sengled's cloud — and binds locally.

Non-interactive form: `--ssid <net> --password <pw>`. Other verified flags: `--ip` (UDP control),
`--mac` (MQTT control), `--diagnose`.

### Step 2 — install the Home Assistant integration

A working integration **ships with the tool**: `SengledTools/custom_components/sengled_udp/`.
Copy it into your HA config and restart:

```bash
cp -r SengledTools/custom_components/sengled_udp <ha-config>/custom_components/
```

Local UDP, no cloud, no broker, no flashing. Each bulb becomes a `light` entity with on/off,
brightness, RGB color, and color temperature. See
[§4](#4-what-you-get-in-home-assistant) for the full surface.

### Practical friction to expect

The pairing flow was historically TLS-fragile — ALPN `x-amzn-mqtt-ca`, narrow TLS 1.2 cipher
selection, and a certificate SAN that breaks when the host IP changes. **PR #63 fixed all three.**

> ### ✅ Three rules that save an evening
> 1. **Use current `master`**, not a release tarball.
> 2. **Give your provisioning host a static LAN IP** so the cert SAN stays valid.
> 3. **Set a DHCP reservation for each bulb.** The integration binds by **IP**, so a new lease
>    silently orphans the config entry.

**If Home Assistant and your bulbs are on different VLANs:** broadcast discovery will not cross the
boundary. Add each bulb **by IP** via the manual step instead. Unicast UDP 9080 reachability is all
that's actually required.

### Why this is trustworthy for *this* model

`SengledTools` **PR #63** was tested on *"W12-N15 bulbs on stock firmware"* and fixed exactly the
out-of-box-activation / credentials-don't-persist failure. **W12-N15 is this bulb.** The
recommended path isn't theoretical here — it's the path someone already debugged on this hardware.

### ⚠️ Avoid the older cloud-proxy integrations

`jfarmer08/ha-sengledapi`, `ripleyeldridge/…`, and `kylev/ha-sengledng` all proxy the **Sengled
cloud API**. Only post-outage designs (`sengled_udp`, `ha-sengled-local`) work, because only they
assume the cloud is unavailable.

---

## 4. What you get in Home Assistant

The UDP protocol is a **smaller subset than Sengled's MQTT protocol**. This section is explicit
about the boundary, because the failure mode of getting it wrong is nasty: if an integration
*declares* a feature the transport can't honour, Home Assistant accepts `transition:` or `effect:`
in your script and **silently discards it** — automations look correct and aren't.

### Verified UDP capability surface

| Capability | Function | Range | Reads back? |
|---|---|---|---|
| Power | `set_device_switch` | 0/1 | inferred, not read |
| Brightness | `set_device_brightness` | 0–100 | ✅ |
| RGB color | `set_device_color` | 0–255 per channel | ⚠️ post-dim duty only |
| Color temp | `set_device_colortemp` | **0–100**, not kelvin | ❌ no getter |
| Per-channel PWM | `set_device_pwm` | `r`,`g`,`b`,`w` 0–100 | ❌ volatile |
| Status (all-in-one) | `search_devices` | — | mac, ip, version, config/bind/mqtt state, R/G/B/W |
| ADC | `get_device_adc` | — | ✅ |
| MAC / firmware | `get_device_mac` / `get_software_version` | — | ✅ |
| Factory mode | `get_factory_mode` / `set_factory_mode` | none on set | ✅ read, one-way write |
| Dimmer curve | `get_dimmer_info` | — | ✅ |
| Reboot / factory reset | `reboot` / `factory_reset` | — | n/a |

### What you get, stock vs extended

The bundled integration covers the light itself. An extended build adds diagnostics and controls —
**22 entities per bulb, 8 enabled by default**, the rest opt-in via the entity registry.

| Capability | HA construct | Stock | Extended |
|---|---|---|---|
| On/off · brightness · RGB · color temp | `light` | ✅ | ✅ |
| Color temp as raw 0–100 | service | ❌ | ✅ |
| Per-channel PWM | service + 4 `number`* | ❌ | ✅ |
| Firmware · ADC · MAC · IP · Last seen | `sensor` | ❌ | ✅ |
| Raw channel duty R/G/B/W | 4 × `sensor`* | ❌ | ✅ |
| MQTT session · cloud-bound · provisioned · factory mode | `binary_sensor` | ❌ | ✅ |
| Identify · reboot · factory reset · enter factory mode | `button` | ❌ | ✅ |
| Dimmer curve | diagnostics download | ❌ | ✅ |
| Arbitrary protocol access | service w/ response | ❌ | ✅ |
| **Availability when the bulb is off** | `available` | ❌ **broken** | ✅ |
| **Device grouping** | `DeviceInfo` | ❌ none | ✅ |

`*` = created disabled-by-default.

> **The most valuable fix is the least glamorous one.** The stock component assigns an internal
> `_available` flag in five places but never defines an `available` property — so `LightEntity`'s
> default (`True`) always won, and **an unplugged bulb still rendered as a working, controllable
> light.** Deriving availability from the update coordinator fixes it.

### What you do NOT get over UDP — and why

| Missing | Why |
|---|---|
| **Effects** | MQTT-only. Absent from the UDP command surface entirely. |
| **Transitions / gradient time** | MQTT-only. Use HA-side transitions instead. |
| **Multi-bulb group commands** | MQTT-only — but unnecessary: use a native **HA light group**, which scenes and voice assistants already understand. |
| **RSSI** | Not in the protocol. `search_devices` returns no signal field. Connectivity is represented by entity availability plus a *Last seen* timestamp. |

### Protocol caveats worth knowing before you build automations

**PWM is volatile.** PWM values are never written to flash, and **any** stateful command
(`set_device_brightness`, `set_device_color`, `set_device_colortemp`, `set_device_switch`) exits
PWM mode and reloads the saved state. So PWM sliders can only ever be assumed-state, and get
clobbered the moment anyone touches the brightness slider. Use the one-shot service, not four
slider writes — four writes make the bulb render three intermediate colors on the way to the
intended one.

*Neat consequence:* an **Identify** button can flash via PWM and then send a no-op
`set_device_brightness` to force PWM exit, which reloads the saved state. Identify is therefore
non-destructive **by construction**.

**Color temperature has an unresolved unit conflict.** `set_device_colortemp` takes 0–100, not
kelvin, and the two available sources disagree about what `0` means — the CLI help says **2700 K**,
the stock integration maps **2000 K**. Until someone photographs a bulb at `percent: 0` next to a
known 2700 K reference, **the warm end of the HA slider may be up to 700 K optimistic.**

**Color read-back is lossy.** The firmware reports post-dimming duty cycles, not the requested
color, so a round-trip would "correct" your color into drift. Both versions cache the last
requested value and prefer it for display.

**On/off is inferred, not read.** There is no `get_device_switch`. Power state is derived from
channel drive plus brightness — reverse-engineered from real hardware, and preserved deliberately.

**ADC has no documented unit.** It returns e.g. `630.73`. Labelling it volts would be a guess, so
it carries `state_class: measurement` and no unit.

### 🛑 One UDP function is deliberately not exposed

`update_led_firmware` takes an `ota_url` and **pushes arbitrary firmware to a module that cannot be
re-flashed over the air.** A dashboard button that can brick a bulb with no recovery path is not
worth the convenience. It remains reachable through a raw-command service, which requires
deliberate intent.

### Group control across several bulbs

```yaml
# configuration.yaml
light:
  - platform: group
    name: All Sengled Bulbs
    entities:
      - light.sengled_bulb_1
      # ...
```

One caveat: a group command becomes **N sequential UDP exchanges**, each with a ~3 s timeout. Eight
*offline* bulbs would mean a 24 s stall. Replies normally arrive in milliseconds — but don't put a
group call in a tight automation loop.

---

## Path 2 — local MQTT server emulation

A heavier alternative to Path 1: run a **full local replacement for Sengled's cloud** and let stock
bulbs connect to it as if nothing had changed.

- [`FalconFour/ha-sengled-local`](https://github.com/FalconFour/ha-sengled-local) — HA integration
  + add-on. Supports all WiFi ("No Hub Required") Sengled bulbs.
- Pairing is still done by **SengledTools**, pointed at the add-on's `/bimqtt` and
  `accessCloud.json` URLs.

**Choose Path 1 unless you specifically want MQTT** — Path 2 needs an add-on plus a Mosquitto
broker, Path 1 needs neither. Path 2's advantage: it speaks the bulb's native MQTT dialect, so it's
the natural fallback if UDP misbehaves, and MQTT exposes effects and group commands that UDP
doesn't.

---

## Path 3 — solderless OTA flash

> ### ❌ Not applicable to this bulb
> This path requires **`2AGN8-WF863` / ESP8266EX**. This bulb is WF864/MX1290 — an ARM core, and
> the shim is an Xtensa binary. Documented here for owners of *other* Sengled models.

On ESP8266 units, flashing open firmware is **also solderless**: `SengledTools` impersonates
Sengled's own cloud and pushes an arbitrary image over WiFi.

```bash
python sengled_tool.py --mac <BULB_MAC> --upgrade "firmware/shim.bin"
```

1. The bulb reboots into **`Sengled-Rescue`**, its own AP. Join it, open `http://192.168.4.1` —
   slow, keep refreshing.
2. **Back up the full flash first** (*full → backup selected*). Your only way home.
3. Flash **Tasmota / ESPHome / WLED** (*boot → choose `.bin` → flash selected*).

**Gotchas:** *"write blocked (overlaps running slot)"* → use **"Relocate to ota_1"**, reboot, retry.
Expect several attempts with power cycles between them (issues #47, #48).

### 🛑 `--force-flash` on a non-ESP8266 module: **do not**

This is the single most dangerous command in this entire document, and it is one flag away from the
happy path. **It is not an "advanced option." It is a brick.**

The tool gates flashing behind a **two-entry allowlist** — `{"W31-N11", "W31-N15"}` — and
`--force-flash` overrides that gate. On a WF864 that means **pushing an Xtensa binary at an ARM
core.**

> **Why the built-in safety net cannot save you:** the shim's own guard — *"Not ESP8266 image slated
> for boot, avoiding brick"* — **executes inside the shim**. The shim is an ESP8266 binary. On an
> MX1290 it never runs at all, so the one check that would have stopped you is the very thing that
> can't execute. **The guard only ever protects an ESP8266.**

If the allowlist blocks your bulb, that is the tool **correctly** telling you your module isn't
supported. Use [Path 1](#path-1--solderless-local-control-recommended).

### 💡 What would unlock solderless flashing for this whole family

**Sengled's OTA transport is chip-agnostic** — it's Sengled's own updater and will deliver any
payload to any of these bulbs. Path 3 isn't blocked by the transport. **It's blocked by the absence
of an MX1290/RTL8710BN build of the `Sengled-Rescue` shim.**

That reframes the problem: the missing piece is **one port of an existing shim to a second
architecture**, which would unlock solderless open firmware for every WF862/WF864/EMW3091 bulb at
once. It's a legitimate upstream feature request against
[`SengledTools`](https://github.com/HamzaETTH/SengledTools) — **not something available today, and
not something to wait on.** If you have RTL8710BN experience, that port is the highest-leverage
contribution available here.

---

## Path 4 — UART flash to open firmware

> **⚠️ Advanced. Unexplored on this specific module. Requires mains-voltage teardown.**
> You do not need this to get the bulb into Home Assistant — [Path 1](#path-1--solderless-local-control-recommended)
> already does that. This is for owning the firmware outright.

**This path is more viable than "MXCHIP" makes it sound.** MX1290 is a **Realtek RTL8710BN
rebadge**, which puts it inside mature, well-trodden tooling:

| Target | Status |
|---|---|
| **ESPHome + LibreTiny** | ✅ Supported. Platform `rtl87xx:`, family `FAMILY_RTL8710B`. Board profiles `generic-rtl8710bn-2mb-468k` / `-788k` — **2 MB matches WF864.** |
| **OpenBeken** | ✅ Supported (`platforms/RTL8710B`). Arguably the *better* fit for an RGBCW bulb — native LED-channel driver, no YAML compile step. |
| **`ltchiptool`** | ✅ The flashing tool for this family. *(Not installed by default — `pipx install ltchiptool`.)* |

### Prior art: none for WF864, strong for the same silicon

- **Sengled WF864 specifically: zero.** GitHub-wide searches for `WF864`, `Sengled+RTL8710`,
  `Sengled+libretiny`, `Sengled+ltchiptool` return nothing relevant. **You would be first.**
- **Closest precedent — and it's a good one:** the **Solis S3 WiFi Stick** is an **MXCHIP EMW3080-E
  = RTL8710BN clone**, flashed with `ltchiptool` + an ESPHome UF2 over a USB-serial adapter on board
  test points. *Same silicon, same module vendor, same tool.* That's the pattern to follow.

### The two things most likely to waste your afternoon

> ### ⚠️ Gotcha #1 — flashing uses **UART2**, not UART0
> On RTL8710BN: **pin 1 = `PA_30` = UART2_TX**, **pin 2 = `PA_29` = UART2_RX**, **pin 12 = `CEN`**.
> MXCHIP's own documentation says ISP programming goes over **UART2 (PA_29/PA_30)**. If the pads
> silkscreened `Tx`/`Rx` turn out to be the UART0 *log* port, **flashing will never handshake no
> matter how perfect your wiring** — verify the pads before blaming the solder.

> ### ⚠️ Gotcha #2 — your adapter probably won't do 1.5 Mbaud
> The download handshake runs at **1.5 Mbaud**. **Use an FT232RL. PL2303 is documented as not
> working.** 3.3 V logic only.

### Download-mode entry

The documented sequence:

1. `CEN` → GND
2. `TX2` → GND
3. release `CEN`
4. release `TX2`
5. Confirm on a serial terminal — garbage / non-letter characters mean you're in download mode.

The module's **`BOOT`** pad is very likely a convenience strap for exactly this. Try it first, then
fall back to the `CEN`+`TX2` dance, which is the authoritative method.

### Two genuine comforts

- **It cannot be software-bricked.** The UART loader lives in **mask ROM**, so even a destroyed
  bootloader is recoverable. This materially lowers the risk.
- **Most failures are electrical, not protocol** — supply voltage droop or loose wiring. Check
  those before doubting your image.

**Dump the stock flash first** (`ltchiptool` read). There is no vendor image to re-download.

> ### 🔒 Your flash dump contains your secrets. Never post it.
> This one catches people, because the natural thing to do when a flash fails is to upload the dump
> to a forum thread or a GitHub issue and ask for help. **Don't.**
>
> On RTL8710BN the dump includes these partitions:
>
> | Partition | Offset | Contains |
> |---|---|---|
> | `kvs` | `0x0F5000` | Key-value store — **your WiFi SSID and password**, and very likely the bulb's per-device Sengled token |
> | `userdata` | `0x0FD000` | Vendor data — same risk |
>
> A dump is a **credential file with a `.bin` extension.** If you need to share a region for
> debugging, share only the region you're actually asking about, and redact anything from those two
> partitions. `.gitignore` in this repo already excludes `*.bin` and `*_backup*` for exactly this
> reason — but treat that as a backstop, not a plan.

### Remaining unknowns

🚧 MX1290 is reported to sometimes ship with **flash encryption and log-UART disabled**. If flash
encryption is enabled on your unit, this path ends there. No pin map exists for the LED channels
either — `UPK2ESPHome`, which extracts GPIO mappings automatically, **only works on Tuya devices**.

> ### ⚠️ Do NOT start from the W31-N15 Tasmota template
> It's a tempting shortcut and it is the **wrong model**: W31-N15 is an **A19 ESP8266** part; this
> is a **BR30 RTL8710BN**. Different chip, different form factor, different board. Its pinout tells
> you nothing about this bulb. Discover the channels empirically instead — drive one candidate pin
> at a time at ~30% and note which LED lights. If nothing lights, suspect a 2-wire constant-current
> driver IC (`sm2135` / `bp5758d` / `bp1658cj` / `my9231`) rather than direct PWM — a Hackaday
> teardown of a Sengled A19 found an **SM1533E**, so Sengled does ship driver ICs.

### ⚠️ MAINS SAFETY — read before opening any bulb ⚠️

> ### 🛑 THE BULB MUST BE UNPLUGGED FROM MAINS. ALWAYS. NO EXCEPTIONS.
> ### 🛑 NEVER connect a USB serial adapter to the bulb while the driver board is energized from AC.

**This is not boilerplate.** A smart bulb's driver is a **non-isolated (transformerless) switch-mode
power supply**. There is **no transformer and no optocoupler** between the AC line and the
low-voltage logic:

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
2. **Wait ≥ 60 seconds** after unplugging before touching the board. The bulk electrolytic capacitor
   (typically 6.8–22 µF / 400 V) holds a lethal charge. **Verify with a DMM in DC volts across the
   bulk cap: it must read < 5 V** before you touch anything. If it holds charge, bleed it through a
   **10 kΩ / ≥ 2 W resistor** — not a screwdriver, which welds and shatters.
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

**⚠️ 3.3 V LOGIC ONLY.** RTL8710BN is **not 5 V tolerant**. If your USB-serial adapter has a
5 V / 3.3 V jumper, set it to **3.3 V and verify with a meter on the TX pin before connecting.**
**Many cheap adapters ship jumpered to 5 V** and will destroy the module.

---

## 8. Ruled out: the Tuya exploits

Everyone tries these first. Here is precisely why neither can work — and the reasoning is
**narrower than usually claimed**.

### `tuya-cloudcutter` — disqualified by **vendor**, not by silicon

> **📝 Correction.** An earlier revision of this document claimed cloudcutter was disqualified on
> *both* silicon and vendor grounds. **The silicon half was wrong.** Cloudcutter's supported list
> includes **Realtek RTL8710BN** — exactly what MX1290 is. The disqualification is real, but it
> rests on **one** reason.

- **The reason it fails: wrong vendor.** Cloudcutter attacks the **Tuya SDK's** cloud-activation
  handshake. Sengled firmware is Sengled's own. There is no Tuya activation flow to impersonate.
  *Even where the chip is in scope, the firmware is not.*
- **Moot regardless.** RTL8710BN is only exploitable running **unpatched Tuya** firmware, and
  **Tuya patched the SDK in February 2022.**

<details>
<summary>Cloudcutter reference details, for when a genuinely Tuya device shows up</summary>

- **Supported chips:** BK7231T, BK7231N (unpatched), RTL8710BN (unpatched, SDK 2.0.0 excluded),
  RTL8720CF (caveats). **Not** ESP8266/ESP8285.
- **Known-patched BK7231N firmware:** 1.1.2, 1.1.12, 1.1.15, 1.3.3, 1.3.8, 1.3.10, 1.5.10, 2.0.15.
- **Host requirements:** Linux + NetworkManager + Docker + sudo, and a **secondary WiFi adapter
  whose driver supports AP mode via `nmcli`** (keep internet on Ethernet). No chipset allow-list is
  published; mac80211-native drivers (`ath9k`, `ath9k_htc`, `mt76`, `rt2800usb`, `brcmfmac`) are the
  safe class, out-of-tree Realtek `rtl8812au`/`8821au` DKMS the flaky class.
- Requires a device **profile** to already exist for your exact device + firmware version.

</details>

### `tuya-convert` — deprecated *and* inapplicable

Patched by Tuya years ago; [`ct-Open-Source/tuya-convert`](https://github.com/ct-Open-Source/tuya-convert)
is archived and unmaintained. It only ever converted old unpatched **Tuya** stock. Moot here
regardless.

### Sengled's own OTA — *this one actually works*

**Sengled's OTA mechanism is exploitable** — that's what makes [Path 3](#path-3--solderless-ota-flash)
possible on ESP8266 units. It's constrained by **module**, not by firmware version.

> **Corrected bottom line:** *"there is no wireless way to flash this bulb"* is **true for
> WF864** — but *"there is no way to flash it at all"* is **false**: wired UART flashing is a real
> target ([Path 4](#path-4--uart-flash-to-open-firmware)). And *"there's no wireless flash for any
> Sengled bulb"* is false too — WF863 owners have one.

---

## 9. Credits & prior art

None of this is my discovery. **Referenced by URL only — nothing is vendored here.**

### The projects that make this possible

| Project | Why it matters |
|---|---|
| **[`HamzaETTH/SengledTools`](https://github.com/HamzaETTH/SengledTools)** | The only serious prior art for these bulbs. Local WiFi onboarding, the `sengled_udp` HA integration, and the `Sengled-Rescue` shim. **Paths 1 and 3 are this project's work.** |
| **[`FalconFour/ha-sengled-local`](https://github.com/FalconFour/ha-sengled-local)** | Local replacement Sengled MQTT server as an HA add-on + integration. Path 2. |
| [LibreTiny](https://docs.libretiny.eu) · [`ltchiptool`](https://github.com/libretiny-eu/ltchiptool) | `realtek-ambz` support — what makes Path 4 a real target rather than a fantasy. |
| [`OpenBK7231T_App`](https://github.com/openshwprojects/OpenBK7231T_App) (OpenBeken) | RTL8710B support with a native LED-channel driver. |
| [ESPHome](https://esphome.io) · [Home Assistant](https://www.home-assistant.io) | Where every path terminates. |
| [`blakadder/templates`](https://github.com/blakadder/templates) | Tasmota template DB. *(No template exists for this bulb — and the W31-N15 one is a different model. See Path 4.)* |

### Context projects — *not* applicable here

[`tuya-cloudcutter`](https://github.com/tuya-cloudcutter/tuya-cloudcutter) ·
[`tuya-convert`](https://github.com/ct-Open-Source/tuya-convert) (archived) ·
[device DB](https://github.com/tuya-cloudcutter/tuya-cloudcutter.github.io) ·
[`bk7231tools`](https://github.com/tuya-cloudcutter/bk7231tools)

*Note: **Tasmota has no BK7231 support at all** — LibreTiny ported ESPHome to Beken; nobody ported
Tasmota. Irrelevant to this bulb, but a common misconception.*

### Research notes

Raw working notes with sourcing and confidence levels are in [`research/`](research/):

| File | Topic |
|---|---|
| [`01-chip-id.md`](research/01-chip-id.md) | Module ID, FCC exhibits, the RTL8710BN discovery, verified UART procedure |
| [`02-ota-path.md`](research/02-ota-path.md) | The no-solder verdict, SengledTools capability matrix, `--force-flash` hazard |
| [`03-uart-flash.md`](research/03-uart-flash.md) | Serial flashing procedures + full mains-safety treatment |
| [`05-ha-features.md`](research/05-ha-features.md) | Full feature → HA entity matrix, protocol caveats, smoke-test plan |

### Tools

[`tools/probe_bulb.py`](tools/probe_bulb.py) — identify a Sengled bulb over UDP. No pairing, no
flashing, no teardown.

---

## Disclaimer

Opening a mains-powered LED bulb exposes you to **lethal voltages**, destroys the bulb's thermal
design and any warranty, and may violate local electrical regulations. Flashing third-party firmware
can permanently brick the device. **You do this at your own risk.** The authors accept no liability
for damage, injury, or death.

**If you are not confident reading the mains-safety rules and following every one of them, use
[Path 1](#path-1--solderless-local-control-recommended)** — no teardown, no soldering, no mains
exposure. For almost everyone it is also simply the better answer.

## License

[MIT](LICENSE) © JP ([@jphein](https://github.com/jphein))
