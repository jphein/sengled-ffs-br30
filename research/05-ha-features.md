# Full Feature Surface → Home Assistant (Path A: SengledTools UDP)

**Status:** COMPLETE — code written and statically verified; **not yet smoke-tested on hardware.**
**Researcher:** Nebula
**Device:** Sengled **W12-N15** BR30 multicolor RGB, E26 (ASIN B097CYHRZJ). "FFS" in the
listing title = Amazon **Frustration-Free Setup**, not a brand.
**Chosen path:** Path A — stock firmware, local UDP control. Module `WF864SM-M6`
= MXCHIP MX1290 = Realtek RTL8710BN, not OTA-flashable → no ESPHome/Tasmota/OpenBeken.
**Enhanced integration:** `<your-workspace>/sengled_udp/`
**Pristine clone:** untouched (verified `git status --porcelain` clean before and after).

> **Publication safety:** this file carries no homelab identifiers — no real SSIDs,
> no private-range addresses from the lab, no internal hostnames, no MACs — and is
> safe to source the public repo's "Features you get in HA" section from. The one
> example entity_id uses a deliberately fictional address. Note that
> `research/04-ha-endstate.md` is **not** clean (see its header banner) — do not
> copy from that one.

> **One correction to the project state notes.** Line 21 describes this work as adding
> "per-channel PWM, diagnostics, reboot/reset buttons, **effects, groups**".
> Effects and group commands are **MQTT-only and absent from the UDP surface** —
> see §0/C1 below. They are deliberately not implemented, and the project state notes's feature
> list should be amended so the public repo does not promise them.

---

## 0. Three corrections to the task brief (verified against source)

### C1. Effects, gradient/transition time, and group control are **NOT available over UDP**

The brief lists these as "capabilities visible in the CLI". They are — but in the
wrong argument group. In `sengled_tool.py` the parser has two groups:

- `control_group = parser.add_argument_group("Bulb Control (MQTT)")` — lines 488-540
- `udp_group = parser.add_argument_group("UDP Control (Local Network)")` — lines 542-606

`--group-macs`, `--group-switch`, `--group-brightness`, `--group-color-temp`,
`--gradient-time` and `--effect-status` all live in the **MQTT** group, and the
source comments mark them `# Group control arguments (untested)` and
`# Effect status (untested)`. `handle_udp_commands()` (command_handler.py:67-197)
never references any of them.

The protocol doc agrees in its first line: *"UDP control is a smaller subset than
MQTT control; use the MQTT reference for advanced features like scenes, effects,
or device management."*

**Consequence:** the enhanced integration must **not** declare
`LightEntityFeature.TRANSITION` or `.EFFECT`. Declaring a feature the transport
cannot honour makes HA accept `transition:`/`effect:` in a script and silently
discard it — worse than not offering it, because automations look correct and
aren't. Group control is served by a native HA light group instead.

### C2. There is no RSSI in the UDP surface

The brief asks for "RSSI/online" as a diagnostic sensor. `search_devices` returns
exactly `ret, mac, ip, config_state, bind_state, mqtt_state, version, R, G, B, W`
— no signal field, and there is no known `get_rssi`-style function. I did not
invent one. Connectivity is represented by **entity availability** plus a
**Last seen** timestamp sensor. If you want to hunt for an undocumented signal
function, `sengled_udp.send_raw` is the tool (see §5).

### C3. Factory mode cannot be modelled as a switch

The brief suggests "switch/select: factory mode". But `set_factory_mode` takes
**no documented parameter** (`{"func":"set_factory_mode","param":{}}`), and there
is no known payload that *leaves* factory mode. A `switch` promises a reversible
two-way toggle that the protocol cannot deliver; its `turn_off` would have to be
a guess. Modelled instead as:

- **binary_sensor** "Factory mode" — the read side, from `get_factory_mode`
- **button** "Enter factory mode" — the one-way action, disabled by default

Reboot is the documented way back.

---

## 1. Verified UDP capability surface

Every row below is confirmed present in `handle_udp_commands()` and/or
`docs/references/UDP_COMMANDS_REFERENCE.md`. Transport: JSON over **UDP :9080**,
`{"func":…,"param":{…}}` → `{"func":…,"result":{"ret":0,"msg":"success",…}}`,
`ret == 0` = success.

| Capability | Function | Params / range | Reads back? |
|---|---|---|---|
| Power | `set_device_switch` | `switch` 0/1 | via channel `freq`/brightness |
| Brightness | `set_device_brightness` | `brightness` 0-100 | ✅ `get_device_brightness` |
| RGB colour | `set_device_color` | `red`/`green`/`blue` 0-255 | ⚠️ only post-dim duty cycles |
| Colour temp | `set_device_colortemp` | `colorTemperature` **0-100** | ❌ no getter |
| Per-channel PWM | `set_device_pwm` | `r`,`g`,`b`,`w` 0-100 | ❌ never (volatile) |
| Status (all-in-one) | `search_devices` | — | mac, ip, version, config/bind/mqtt state, R/G/B/W |
| ADC | `get_device_adc` | — | ✅ float, e.g. `630.73` |
| MAC | `get_device_mac` | — | ✅ |
| Firmware version | `get_software_version` | — | ✅ |
| Factory mode | `get_factory_mode` / `set_factory_mode` | none on set | ✅ read, one-way write |
| Dimmer curve | `get_dimmer_info` | — | ✅ `dimer,max,count,adc[]` |
| Reboot | `reboot` (alias `set_device_reboot`) | — | n/a |
| Factory reset | `factory_reset` (alias `set_factory_reset`) | — | n/a |
| LED firmware OTA | `update_led_firmware` | `ota_url` | n/a — **not exposed**, see §6 |
| Discovery | `search_devices` broadcast | — | used by stock config_flow |

Known-dead functions (documented, deliberately unused): `set_device_rgb` and
`set_device_mac` send **no reply at all**; `set_device_light` errors
`{"ret":1,"msg":"get b error"}`.

---

## 2. Capability → HA construct matrix (stock vs enhanced)

`*` = created disabled-by-default (opt in via the entity registry).

| Capability | HA construct | Stock | Enhanced |
|---|---|---|---|
| On/off | `light` | ✅ | ✅ |
| Brightness | `light` brightness | ✅ | ✅ |
| RGB colour | `light` `ColorMode.RGB` | ✅ | ✅ |
| Colour temp (kelvin) | `light` `ColorMode.COLOR_TEMP` | ✅ | ✅ |
| Colour temp (raw 0-100) | service | ❌ | ✅ `set_color_temp_percent` |
| Per-channel PWM | service + `number`* | ❌ | ✅ `set_pwm` + 4 numbers* |
| Firmware version | `sensor` | ❌ | ✅ + `sw_version` on the device |
| ADC | `sensor` | ❌ | ✅ |
| MAC | `sensor`* + device `connections` | ❌ | ✅ |
| IP | `sensor`* | ❌ | ✅ |
| Last seen | `sensor`* (timestamp) | ❌ | ✅ |
| Raw channel duty R/G/B/W | 4 × `sensor`* | ❌ | ✅ |
| MQTT session state | `binary_sensor` (connectivity) | ❌ | ✅ |
| Cloud bound | `binary_sensor` | ❌ | ✅ |
| Provisioned | `binary_sensor`* | ❌ | ✅ |
| Factory mode (read) | `binary_sensor` | ❌ | ✅ |
| Factory mode (enter) | `button`* | ❌ | ✅ |
| Reboot | `button` (device_class restart) | ❌ | ✅ |
| Identify | `button` | ❌ | ✅ |
| Factory reset | `button`* | ❌ | ✅ |
| Dimmer info | diagnostics download | ❌ | ✅ |
| Arbitrary protocol access | service w/ response | ❌ | ✅ `send_raw` |
| **Availability when offline** | `available` | ❌ **broken** | ✅ |
| **Device grouping** | `DeviceInfo` | ❌ none | ✅ |
| Effects | — | ❌ | ❌ **MQTT-only, see C1** |
| Transition/gradient | — | ❌ | ❌ **MQTT-only, see C1** |
| Multi-MAC group | — | ❌ | ❌ **MQTT-only; use an HA light group** |
| RSSI | — | ❌ | ❌ **not in protocol, see C2** |

### The two structural gaps in the stock component

1. **Availability was silently broken.** `light.py` assigns `self._available` in
   five places but never defines an `available` property, so `LightEntity`'s
   default (`True`) always won — an unplugged bulb still rendered as a working,
   controllable light. `CoordinatorEntity` fixes this by deriving availability
   from `last_update_success`.
2. **No `DeviceInfo` at all.** Entities were loose, with no device to attach
   sensors/buttons to. Adding diagnostics without first adding a device would
   have produced 22 orphaned entities per bulb.

---

## 3. What I built

`<your-workspace>/sengled_udp/`

| File | New? | Purpose |
|---|---|---|
| `const.py` | new | domain, port, all `func` names, kelvin endpoints, service names |
| `api.py` | new | `SengledUdpClient` — async UDP with per-host lock + reply validation |
| `coordinator.py` | new | `SengledCoordinator` — one poll per bulb feeds every platform |
| `entity.py` | new | shared base: device grouping + unique_id |
| `light.py` | rewritten | coordinator-backed; registers the three services |
| `sensor.py` | new | 9 diagnostic sensors |
| `binary_sensor.py` | new | 4 state flags |
| `button.py` | new | identify / reboot / factory mode / factory reset |
| `number.py` | new | 4 volatile PWM sliders (opt-in) |
| `diagnostics.py` | new | HA "Download diagnostics" incl. live `get_dimmer_info` |
| `services.yaml` | new | UI-visible service definitions with selectors |
| `manifest.json` | edited | `iot_class` → `local_polling`, `integration_type: hub`, v1.1.0 |
| `README.md` | rewritten | install + capability summary |
| `config_flow.py` | **unchanged** | stock discovery/pairing flow works as-is |
| `translations/en.json` | unchanged | — |

**Entity count:** 22 per bulb, of which **8 are enabled by default**
(light, Firmware, ADC, MQTT session, Cloud bound, Factory mode, Identify, Reboot)
and 14 are opt-in. At 8 bulbs: 64 enabled, 176 total registry entries.

### Design decisions worth knowing

**One coordinator per bulb.** The stock component polled from inside
`LightEntity.async_update` — 2 datagrams per bulb. Naively adding 21 more
entities would have multiplied that by 22. The coordinator makes packet count
independent of entity count: **4 datagrams per bulb per 30 s**
(`search_devices`, `get_device_brightness`, `get_device_adc`,
`get_factory_mode`), with `get_software_version` fetched once and cached.

Honest accounting: that is 2× the stock *absolute* traffic (32 packets/30 s
across 8 bulbs ≈ 1/s) for 22× the entities. Raise
`DEFAULT_SCAN_INTERVAL` in `const.py` if you want it quieter.

**The protocol has no request ID.** Replies are correlated only by the echoed
`func` name, so two in-flight commands to one bulb can have their replies
swapped. `api.py` defends twice: an `asyncio.Lock` per host serialises
exchanges, and any reply whose `func` doesn't match the request is discarded.
The stock component did neither.

**Device identity is keyed on host, not MAC.** MAC is unknown until the first
successful poll, and changing `identifiers` later would orphan the device and
create a duplicate. Host (the config entry's own key) is the identifier; MAC is
attached via `connections` once learned.

**PWM is a service first, entities second.** See §4 — the number entities exist
because they were asked for, but the service is the correct construct.

---

## 4. Protocol caveats that shaped the design

### PWM is volatile — this is the big one

From the protocol reference, confirmed in the CLI help text:

- PWM values are **never persisted to flash**.
- **Any** stateful command exits PWM mode: `set_device_brightness`,
  `set_device_color`, `set_device_colortemp`, `set_device_switch`. On exit the
  firmware **reloads its saved state**, discarding the PWM values.
- `search_devices` **cannot read PWM back** — it returns cached RGB/colortemp.

So a `number` entity for PWM can never be anything but assumed-state, and will be
silently clobbered the moment anyone touches the light's brightness slider — the
same light entity, same device. That is why:

- `sengled_udp.set_pwm` (one datagram, all four channels) is the primary
  interface. Four separate slider writes would make the bulb render three
  intermediate colours en route to the intended one.
- the four `number` entities are **disabled by default**, `assumed_state=True`,
  and documented as bench tools for identifying which physical LED a channel
  drives.

**Identify turns this bug into a feature.** It flashes via `set_device_pwm`, then
sends `set_device_brightness` with the bulb's *current* brightness — a no-op
change whose only purpose is to force PWM exit, which reloads the saved state.
Identify is therefore non-destructive by construction.

### Colour temperature: a genuine unit conflict, unresolved

`set_device_colortemp` takes an integer **0-100**, not kelvin. The two available
sources disagree about what 0 means:

- SengledTools CLI help: *"Set color temperature (0-100 percent; **0=2700K**, 100=6500K)"*
- Stock HA integration: mapped **2000K**-6500K onto 1-100

I kept **2000 K** (`MIN_KELVIN` in `const.py`) so behaviour does not regress for
existing users, and left it as a one-line constant. To settle it empirically:
set `sengled_udp.set_color_temp_percent` to 0, photograph the bulb next to a
known 2700 K reference, and adjust. Until then the warm end of the HA slider may
be up to 700 K optimistic.

### Colour read-back is lossy

The firmware reports **post-dimming duty cycles**, not the requested colour, so a
round-trip would "correct" the user's colour into drift. Both stock and enhanced
versions cache the last requested RGB/kelvin and prefer it for display. There is
no `get` for colour temperature at all — the cached request is the only honest
answer, and it is `None` after a restart until something sets it.

### On/off is inferred, not read

There is no `get_device_switch`. Power state is derived from an empirical rule
(`freq == 0` on a channel means that channel is actively driven), with brightness
`== 0` as an override and non-zero channel duty as a fallback. Inherited from the
stock component; preserved deliberately because it was reverse-engineered from
real hardware.

### ADC has no units

`get_device_adc` returns e.g. `630.73` with no documented unit, and its reply
omits `ret` entirely (the client tolerates a missing `ret` as success). The
sensor therefore declares `state_class: measurement` but **no** device class or
unit — labelling it volts would be a guess.

---

## 5. Discovering more of the protocol

`sengled_udp.send_raw` returns the bulb's raw reply, including errors, which is
exactly what protocol probing needs:

- unknown function → `{"result":{"ret":1,"msg":"function not find"}}`
- **real** function, bad params → a function-specific error, e.g.
  `{"func":"set_device_brightness","result":{"ret":1,"msg":"get brightness error"}}`

That difference is the oracle: any name that does *not* say "function not find"
exists. Candidates worth trying: `get_hardver` (appears in the docs' examples but
in no command table), and anything RSSI/wifi-shaped.

```yaml
action: sengled_udp.send_raw
target:
  entity_id: light.sengled_bulb_192_168_1_50
data:
  func: get_hardver
  param: {}
```

Run it from Developer Tools → Actions with "Response variable" set to see the reply.

---

## 6. Deliberately not exposed

- **`update_led_firmware`** (`ota_url`) — pushes arbitrary firmware to a
  non-flashable module. A dashboard button that can brick a bulb, with no
  recovery path (per Path A the module cannot be re-flashed over UART), is not
  worth the convenience. Reachable via `send_raw` if ever needed, which requires
  deliberate intent.
- **`set_device_mac`** — no reply, unclear semantics, changes device identity.
- **`set_device_rgb`** / **`set_device_light`** — dead or broken; `set_device_color`
  is the working equivalent.

---

## 7. Install

Copy-by-folder, no HACS needed:

```bash
# to HAOS via Samba/SSH add-on, or into a mounted config dir
cp -r <your-workspace>/sengled_udp \
      <ha-config>/custom_components/
```

Then restart Home Assistant.

- **Existing config entries keep working.** The entry data shape
  (`hosts`, `name_prefix`, `host_types`) is unchanged and `config_flow.py` is
  untouched, so no re-pairing.
- **Entity IDs for the light are preserved** — `unique_id` is still
  `{entry_id}_{host}`. New entities get `{entry_id}_{host}_{key}`.
- One behaviour change to expect: the light will now correctly go
  **unavailable** when a bulb stops answering, where before it always looked online.
- Enable the opt-in entities under Settings → Devices → *bulb* → +N entities not shown.

### Verification status

- `python3 -m py_compile` — **all 10 modules pass**.
- `manifest.json` valid JSON; `services.yaml` valid YAML (3 services parsed).
- AST check: every `from .const import …` name resolves; no unused imports;
  every `coordinator.*` reference used by a platform exists on `SengledCoordinator`.
- **Not verified:** runtime behaviour against Home Assistant or real hardware.
  `homeassistant` is not installed on this workstation, so HA API compatibility
  (entity-service registration signature, `SupportsResponse`, frozen-dataclass
  entity descriptions) is checked by inspection against current-gen HA patterns
  only. First load in HA is the real test — watch the log for import errors.

---

## 8. Group control across 8 bulbs

The MQTT `--group-macs` path is unavailable over UDP, and re-implementing it is
unnecessary: HA's native light group already fans a single command out to N
entities, and is understood by scenes, voice assistants and adaptive-lighting.

```yaml
# configuration.yaml
light:
  - platform: group
    name: All Sengled Bulbs
    entities:
      - light.sengled_bulb_1
      # ... through 8
```

`sengled_udp.set_pwm` and `send_raw` also accept multiple targets (entity, device
or area) and fan out, since they are registered as entity services.

One caveat: a group command becomes **N sequential UDP exchanges**, each with a
3 s timeout. Eight offline bulbs would mean a 24 s stall. In practice replies
arrive in milliseconds — but do not put a group call in a tight automation loop.

---

## 9. Smoke-test plan for bulb #1

Prerequisites: the bulb and Home Assistant must share an L2 broadcast domain, or
at least have unicast UDP:9080 reachability between them. Broadcast **discovery**
in the config flow will not cross a VLAN boundary — if HA and the bulb are on
different segments, add the bulb by IP via the manual step instead. A DHCP
reservation per bulb is strongly recommended: the integration binds by IP, so a
new lease silently orphans the config entry.

Run these in order; each one isolates a different layer.

**1 — transport, before HA is involved.** From any host that can route to the bulb:

```bash
python3 - <<'EOF'
import json, socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(3)
s.sendto(json.dumps({"func":"search_devices","param":{}}).encode(), ("<BULB_IP>", 9080))
print(s.recvfrom(2048)[0].decode())
EOF
```

Expect `ret:0` plus `mac`, `version`, and `R`/`G`/`B`/`W` objects. **Record this
reply verbatim** — it is the ground truth for everything below.

**2 — does the model parse?** The device page's *Model* is derived by splitting the
firmware string on `_` and taking field 2. Upstream's captured example is
`…_W21-N13_SYSTEM_…` → `W21-N13`. For a W12-N15 bulb it should read `W12-N15`.
If Model is blank or garbled, `_model_from_version()` in `coordinator.py` needs
adjusting for this firmware's naming.

**3 — channel count settles an open question.** Count the channel keys in step 1's
reply. Four (`R`,`G`,`B`,`W`) confirms RGBW; a fifth would mean true RGBCW and the
colour handling needs revisiting. the project state notes calls the bulb "multicolor RGB", which
is consistent with four.

**4 — the availability fix.** Power the bulb off at the wall. Within ~30 s every
entity should go **unavailable**. This is the one behaviour that provably differed
from stock (which always reported online), so it is the highest-value single check.

**5 — colour-temperature calibration** (the one unresolved conflict, §4). Call
`sengled_udp.set_color_temp_percent` with `percent: 0`, then `50`, then `100`, and
compare against a known 2700 K reference. If `0` looks like 2700 K rather than
2000 K, change `MIN_KELVIN` in `const.py` to `2700`.

**6 — PWM volatility, to confirm the documented behaviour is real.** Call
`sengled_udp.set_pwm` with `red: 100` only; the bulb should go red. Now move the
brightness slider — the red should **vanish** and the saved state return. If it
persists, the volatility caveat is wrong for this firmware and the PWM number
entities could be promoted out of opt-in.

**7 — Identify.** Press it. Expect three white flashes, then a return to whatever
the bulb was doing before, with no state change left behind.

**8 — protocol probing.** `sengled_udp.send_raw` with `func: get_hardver` (present
in upstream's examples but in no command table) and with a deliberate nonsense
name. The nonsense name must return `"function not find"`; anything else means the
oracle in §5 is unreliable on this firmware.

**Most likely failure mode:** an HA-side import error on first load rather than a
protocol problem, since HA API compatibility is the unverified axis (§7). Check
Settings → System → Logs for `custom_components.sengled_udp` immediately after
restart, before concluding anything about the bulb.
