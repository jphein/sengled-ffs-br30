# Sengled Local Server (Home Assistant add-on)

Replacement cloud endpoints + MQTT broker for Sengled Wi-Fi bulbs, running **on
Home Assistant** so bulbs on an isolated IoT VLAN can reach it.

Wraps the server code from [SengledTools](https://github.com/HamzaETTH/SengledTools)
(cloned at build time, pinned revision) rather than reimplementing the protocol,
so wire behaviour matches the tool you pair with.

## What it does

| Piece | Detail |
|---|---|
| `POST /life2/device/accessCloud.json` | Answers the bulb's boot-time cloud check |
| `GET /jbalancer/new/bimqtt` | Tells the bulb which MQTT broker to use |
| Embedded MQTT broker | `amqtt`, TLS, anonymous, no client certs — what bulbs connect to |
| Bridge (optional) | Relays `wifielement/#` to/from Home Assistant's Mosquitto |

## Why it must run on Home Assistant

During pairing, SengledTools writes **absolute URLs** into the bulb
(`appServerDomain`, `jbalancerDomain`) and the bulb **persists them**. Whatever
address is baked in is what the bulb calls for the rest of its life.

If your IoT VLAN cannot route to your workstation's VLAN, a workstation address
is permanently unreachable — so the server has to live somewhere the bulbs can
reach, and `advertised_host` must name that interface.

## Install

Copy this folder into Home Assistant's local add-on directory and restart the
Supervisor:

```
/addons/sengled_local/
```

Then Settings → Add-ons → Add-on Store → ⋮ → *Check for updates*; "Sengled Local
Server" appears under **Local add-ons**. Install, configure, start.

## Configuration

```yaml
advertised_host: "<HA_IP>"    # REQUIRED: the HA IP that faces your bulbs
http_port: 57542              # SengledTools' default; keeps its CLI defaults working
mqtt_port: 18883              # NOT 8883 — see below
bridge_enabled: true
bridge_host: "core-mosquitto"
bridge_port: 1883
bridge_username: ""           # an HA user permitted on Mosquitto
bridge_password: ""
log_level: "info"
```

**`advertised_host` is required and cannot be auto-detected.** The add-on runs
bridge-networked, so it cannot see which host interface faces the bulbs — and on
a multi-homed HA box, guessing would pick the default route, usually the wrong
leg. The add-on refuses to start rather than advertise an unreachable address.

**Why MQTT is on 18883 and not 8883.** The official Mosquitto add-on binds host
ports **1883, 1884, 8883 and 8884** — so *both* conventional TLS-MQTT ports are
already taken on a typical Home Assistant box, and mapping either would make this
add-on fail to start. Since the bulb is *told* which port to use in the bimqtt
reply, an unconventional port costs nothing. Change it only if 18883 clashes with
something of your own, and change the `ports:` mapping to match.

## Pairing bulbs against it

Start this add-on **first**, then pair from a machine joined to the bulb's own
SoftAP, pointing the embedded URLs at Home Assistant:

```bash
python sengled_tool.py --setup-wifi \
  --ssid YOUR_IOT_SSID --password YOUR_IOT_PASSWORD \
  --http-server-ip <HA_IP_FACING_BULBS> \
  --http-port 57542 \
  --broker-ip <HA_IP_FACING_BULBS>
```

⚠️ **Expect the wizard to report a verification timeout even when pairing
worked.** It waits on `http://127.0.0.1:57542/status` — its own local server —
but the bulb's callbacks land on *Home Assistant*. Confirm success in this
add-on's log (you want to see both endpoints served), not in the wizard.

## Bulb control

This add-on does not create entities. Pair it with the enhanced `sengled_udp`
custom integration (UDP :9080) for lights and diagnostics. Once bridged, the
MQTT surface also becomes reachable from HA on `wifielement/{MAC}/update`, which
carries capabilities UDP does not have — gradient/transition timing, effects and
group commands.

## Bridge topic behaviour

- **Bulb → HA:** everything under `wifielement/#` **except** `*/update`
- **HA → bulbs:** only `wifielement/+/update`

The directions are deliberately disjoint so a relayed message cannot loop back.
Publish control commands to `wifielement/{MAC}/update` on HA's broker.
