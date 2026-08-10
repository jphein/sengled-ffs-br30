# Our Own Sengled HA App — Local Replacement Cloud, on Home Assistant

**Status:** BUILT — syntax-clean and logic-tested with stubs; **not yet run against a live bulb.**
**Sourcing:** read from upstream source and verified against a real deployment.
**Add-on:** `<your-workspace>/sengled-local-addon/`
**Control integration (separate, already built):** `<your-workspace>/sengled_udp/`

> **Publication safety:** this file uses placeholders only — no real SSIDs, no lab
> addresses, no internal hostnames, no MACs. Safe to source public docs from.

---

## 0. The finding that reframes this whole task

**The MQTT transport carries the features UDP could not.**

In `05-ha-features.md` I reported that effects, gradient/transition timing and
multi-MAC group control were unavailable — true, but only of the **UDP**
transport. `docs/references/MQTT_COMMANDS_REFERENCE.md` has a
**"Gradient/Transition Control"** section and audio/video/game-sync effect
commands, all published to `wifielement/{MAC}/update`.

Those capabilities were never missing from the *bulb*. They were missing from the
*pipe*. Standing up this MQTT broker is what makes them reachable — so this
add-on is not just plumbing to keep bulbs quiet, it is the path to the feature
set that was previously written off.

**Second finding: the add-on is load-bearing for pairing, not optional polish.**
`sengled/wifi_setup.py:413-414` writes **absolute URLs** into the bulb during
provisioning:

```python
"appServerDomain": f"http://{http_host}:{http_port}/life2/device/accessCloud.json",
"jbalancerDomain": f"http://{http_host}:{http_port}/jbalancer/new/bimqtt",
```

The bulb **persists** these. Whatever address is baked in is called for the rest
of the bulb's life. Pairing from a workstation on the admin VLAN would burn in an
address that the IoT VLAN's firewall policy can never reach — and the only fix
is re-pairing. This is exactly the constraint that forces the server onto Home
Assistant.

---

## 1. Architecture

```
   ┌──────────────── IoT VLAN (bulbs) ────────────────┐
   │                                                  │
   │   bulb ──1── HTTP  :57542  ──┐                    │
   │    │         (accessCloud +  │                    │
   │    │          bimqtt)        │                    │
   │    └──2── MQTT/TLS :18883 ─┐ │                    │
   │          wifielement/#     │ │                    │
   └────────────────────────────┼─┼────────────────────┘
                                │ │
                    ┌───────────▼─▼──────────────┐
                    │  Home Assistant host       │
                    │  (interface facing bulbs)  │
                    │                            │
                    │  ┌──────────────────────┐  │
                    │  │ ADD-ON sengled_local │  │
                    │  │  SetupHTTPServer     │  │  <- upstream code
                    │  │  EmbeddedBroker      │  │  <- upstream code
                    │  │  MqttBridge          │  │  <- ours
                    │  └──────────┬───────────┘  │
                    │             │ 3            │
                    │      ┌──────▼───────┐      │
                    │      │  Mosquitto   │      │
                    │      └──────┬───────┘      │
                    │             │              │
                    │      ┌──────▼──────────┐   │
                    │      │  Home Assistant │   │
                    │      │  core           │   │
                    │      └──────▲──────────┘   │
                    │             │ 4            │
                    │   ┌─────────┴───────────┐  │
                    │   │ sengled_udp         │  │
                    │   │ custom integration  │──┼──── UDP :9080 ──> bulbs
                    │   └─────────────────────┘  │
                    └────────────────────────────┘

1. Bulb boots, calls its persisted URLs. bimqtt reply names the MQTT broker.
2. Bulb opens MQTT/TLS to the advertised host:port. Telemetry on wifielement/#.
3. Bridge relays bulb topics <-> HA's Mosquitto (loop-safe, disjoint directions).
4. Entities come from the sengled_udp integration over UDP, independent of 1-3.
```

**The two planes are independent.** Control/entities ride UDP:9080 and work with
the add-on stopped. The add-on's job is (a) satisfy the bulb's cloud check so
pairing completes and the bulb stops retrying, and (b) expose the richer MQTT
command surface. Nothing in `sengled_udp` depends on the add-on running.

That independence is deliberate: a bug in the replacement cloud must not be able
to take the lights out.

---

## 2. Components

Upstream classes are **imported, not reimplemented**, so wire behaviour cannot
drift from the tool used to pair the bulbs.

| Component | Source | Role |
|---|---|---|
| `SetupHTTPServer` | upstream `sengled/http_server.py` | serves the two endpoints |
| `EmbeddedBroker` | upstream `sengled/mqtt_broker.py` | amqtt, TLS, anonymous |
| `ConfigurablePortBroker` | **ours** (`server.py`) | subclass; makes the bind port settable |
| `MqttBridge` | **ours** (`bridge.py`) | loop-safe relay to Mosquitto |
| `server.py` / `run.sh` | **ours** | wiring, options, lifecycle |

### Exact protocol behaviour (read from the source, not assumed)

`POST|PUT /life2/device/accessCloud.json` →
```json
{"messageCode":"200","info":"OK","description":"正常","success":true}
```

`GET|POST /jbalancer/new/bimqtt` →
```json
{"protocal":"mqtt","host":"<advertised_host>","port":<mqtt_port>}
```

⚠️ `"protocal"` is **misspelled in the real protocol**. Preserved verbatim —
"fixing" it would break the bulb. This is a reason to import upstream's handler
rather than write our own.

The broker: amqtt, TLS, `allow_anonymous: true`, and upstream **patches amqtt's
SSL context creation** so client certificates are *not* required
(`_no_client_auth_create_ssl_context`) — bulbs present none. Certificates are a
self-signed CA generated locally, which tells us something useful: **the bulbs
cannot be validating the server certificate**, or a randomly generated local CA
could never work on them.

### Two upstream behaviours I verified rather than trusted

- **`SetupHTTPServer`'s docstring claims it "stops after both endpoints have been
  hit at least once."** It does not. `start()` spawns `serve_forever` on a daemon
  thread and nothing auto-stops it; only the wizard's explicit `stop()` does. So
  running it as a long-lived daemon is safe. Had the docstring been accurate, this
  design would not work.
- **The broker port is hardcoded** to `0.0.0.0:8883` via the `BROKER_TLS_PORT`
  module constant. That is the same port Home Assistant's Mosquitto add-on uses
  for *its* TLS listener. `ConfigurablePortBroker` overrides `_build_config()` to
  make it settable — chosen over monkeypatching the upstream constant so the
  change stays local and visible. (The port must be assigned before delegating to
  `super().__init__`, because the parent calls `_build_config()` from its own
  constructor.)

### Bridge loop prevention

A naive bidirectional relay on `wifielement/#` ping-pongs forever: HA publishes
`.../update` → bulb-side client is subscribed to `#` so it echoes up → HA-side
client is subscribed to `.../update` so it echoes down → repeat until something
falls over.

Rather than deduplicate messages (stateful, and fragile under QoS-1 redelivery),
the directions are given **provably disjoint topic sets**:

| Direction | Topics |
|---|---|
| bulbs → HA | everything under `wifielement/#` **except** `*/update` |
| HA → bulbs | **only** `wifielement/+/update` |

No topic is eligible both ways, so a round trip is impossible by construction.
The only cost is that HA does not see its own commands echoed back — no loss,
since HA published them.

---

## 3. How bulbs get pointed at Home Assistant

The whole scheme hinges on three flags at pairing time. From
`wifi_setup.py:137` the advertised host is
`getattr(args, "http_server_ip", None) or lan_ip_before_ap` — i.e. **without
`--http-server-ip` it defaults to the pairing machine's own LAN IP**, which is
the wrong answer on a segmented network.

| Flag | Purpose | Value |
|---|---|---|
| `--http-server-ip` | host embedded in the two persisted URLs | HA's bulb-facing IP |
| `--http-port` | port embedded in those URLs | `57542` (add-on default) |
| `--broker-ip` | MQTT host handed to the bulb | HA's bulb-facing IP |

Procedure:

1. **Start the add-on first**, with `advertised_host` = HA's bulb-facing IP.
2. Factory-reset the bulb so it raises its SoftAP (`Sengled_Wi-Fi Bulb_XXXX`).
3. Join that SoftAP from the pairing machine (gateway `192.168.8.1`).
4. Run:

```bash
python sengled_tool.py --setup-wifi \
  --ssid YOUR_IOT_SSID --password YOUR_IOT_PASSWORD \
  --http-server-ip <HA_IP_FACING_BULBS> \
  --http-port 57542 \
  --broker-ip <HA_IP_FACING_BULBS>
```

5. Watch the **add-on log** for both endpoints being served.
6. Give the bulb a DHCP reservation, then add it in `sengled_udp`.

### ⚠️ The wizard will report failure even when it succeeds

`wifi_setup.py:487` polls `http://127.0.0.1:57542/status` — **its own** local
HTTP server — to decide whether pairing verified. It also refuses to count hits
from loopback (`_should_count_hit`). But with `--http-server-ip` pointing at Home
Assistant, the bulb's callbacks land *there*, so the local `/status` never flips
and the wizard times out after ~180 s.

**Pairing has still worked.** Judge by the add-on log, not the wizard. This is a
consequence of splitting the advertised host from the machine running the wizard,
and it is unavoidable without patching upstream.

---

## 4. Install

```bash
# copy into HA's local add-on directory (Samba/SSH add-on, or a mounted config)
cp -r <your-workspace>/sengled-local-addon \
      /addons/sengled_local
```

Settings → Add-ons → Add-on Store → ⋮ → *Check for updates*. "Sengled Local
Server" appears under **Local add-ons**. Configure, then start.

```yaml
advertised_host: "<HA_IP_FACING_BULBS>"   # REQUIRED
http_port: 57542
mqtt_port: 18883       # NOT 8883/8884 — Mosquitto owns both
bridge_enabled: true
bridge_host: "core-mosquitto"
bridge_port: 1883
bridge_username: "<an HA user allowed on Mosquitto>"
bridge_password: "<that user's password>"
log_level: "info"
```

### Design decisions you may need to override

**`advertised_host` is mandatory and the add-on refuses to start without it.**
It runs bridge-networked, so it cannot see which host interface faces the bulbs;
and upstream's `get_local_ip()` uses the "connect to 8.8.8.8" trick, which
returns whatever the *default route* uses — on a multi-homed HA box, reliably the
wrong leg. Because bulbs persist this value, a wrong guess costs a re-pair of
every bulb. Failing loudly beats silently baking in a dead address.

**`host_network: false` on purpose.** Host networking would inherit every HA
interface and race whatever already owns 8883. Explicit port mappings surface the
collision at start-up instead of producing a half-working bind.

**MQTT defaults to 18883, not 8883 — and this was a real deploy blocker.**
Verified against the official Mosquitto add-on's `config.yaml`: it binds host
ports **1883, 1884, 8883 and 8884**. So upstream's hardcoded 8883 *and* the
obvious fallback of 8884 are both already taken on a typical HA box, and either
mapping would make this container fail to start on first launch. Because the bulb
is *told* the port in the bimqtt reply, an unconventional port costs nothing.
Precedent: the FalconFour add-on used 28527 for MQTT and 54448 for HTTP, good
evidence that bulbs honour arbitrary advertised ports.

**Upstream is cloned at build time, not vendored.** SengledTools ships **no
LICENSE file**, so its source carries no granted redistribution permission
(default: all rights reserved). Cloning at a pinned ref
(`build.yaml: SENGLEDTOOLS_REF`) means the user's own machine fetches upstream
and we redistribute nothing. Relevant if any of this reaches a public repo.

---

## 5. What is UNVERIFIED

Nothing here has met a bulb. Ranked by how likely it is to bite:

1. **Whether the W12-N15 / RTL8710BN bulb works with SengledTools at all.**
   Upstream's own `constants.py` lists `SUPPORTED_TYPECODES = {"W31-N11",
   "W31-N15"}` and `COMPATIBLE_IDENTIFY_MARKERS = ("ESP8266",)`. **Our bulb is
   neither** — it is W12-N15 on a Realtek RTL8710BN. That matrix is worded as
   being about firmware flashing ("the only models we can guarantee will work
   with firmware flashing"), and the comments suggest MQTT/UDP control is
   expected to work more broadly — but W12-N15 is unlisted, and `--setup-wifi`
   may refuse or misbehave. `--force-flash` exists for the flashing gate; there
   may be no equivalent for provisioning. **This is the single biggest risk to
   Path A end-to-end and it is upstream's, not ours.**
2. **Whether the bulb accepts a non-8883 MQTT port.** This was a conditional risk
   until the Mosquitto port collision forced 18883 to be the *default* — so the
   unconventional port is now on the happy path, not the fallback, and this moved
   from "if we have to" to "always". The mechanism says it must work (the port is
   handed to the bulb in the bimqtt reply, and FalconFour's add-on used 28527),
   but it is now load-bearing. **If bulb #1 provisions but never opens an MQTT
   session, test this first:** set `mqtt_port: 8883`, stop the Mosquitto add-on to
   free the port, and retry. That isolates "bulb ignores advertised port" from
   every other failure cause.
3. **Whether the bulb tolerates our TLS certificate.** Inference says yes (a
   locally generated CA cannot be pinned), but "does not validate" is deduced
   from upstream's design, not observed on this model.
4. **Whether the bridge sees any traffic.** The topic names come from upstream's
   docs (`wifielement/{MAC}/update|status`). If this firmware uses a different
   prefix, the subscriptions need adjusting — check the add-on log at `debug`.
5. **The MQTT feature unlock (§0).** Gradient/effects/groups are documented
   upstream and marked *untested* there too. Reaching them requires a bulb with a
   live MQTT session.
6. **HA add-on plumbing** — base-image tag availability, `bashio` option
   rendering, apk package names (`py3-cryptography`, `py3-psutil`). These fail
   loudly at build/start, not subtly.
7. **Cert SAN mismatch.** `generate_certificates()` puts the *container's* IP in
   the SAN, not `advertised_host`, and regenerates when it drifts. Harmless if the
   bulb does not validate (see 3), but it means pointless cert churn on restarts.

### What IS verified

- `py_compile` clean: `server.py`, `bridge.py`. `bash -n` clean: `run.sh`.
- `config.yaml` / `build.yaml` valid YAML; **`options` and `schema` keys match
  exactly** (a mismatch is a classic add-on start-up failure).
- **Logic-tested with stubbed `sengled`/`paho` modules:**
  - port override produces `0.0.0.0:8884` and preserves the `ssl` flag;
  - loop breaker drops `wifielement/AA/update` upstream while passing
    `status`/`consumption`, and relays `update` downstream — directions
    confirmed disjoint;
  - `main()` exits non-zero when `advertised_host` is unset.

---

## 6. Recommended bring-up order

Because two independent planes are involved, test them separately or you will not
know which one failed.

1. **UDP plane first, add-on stopped.** Pair bulb #1 by whatever means works, get
   `sengled_udp` controlling it. If this works, you have lights — the valuable
   half — regardless of the add-on.
2. **Then the add-on.** Start it, reboot the bulb, and watch for the two
   endpoints being served in the log. That alone proves the persisted URLs point
   at HA and the firewall path is open.
3. **Then the bridge.** `mosquitto_sub -t 'wifielement/#'` on HA's broker. Any
   traffic proves the relay and confirms the topic prefix.
4. **Then MQTT features.** Publish a gradient/effect command to
   `wifielement/{MAC}/update` and see whether the bulb honours it. This is the
   payoff from §0 and the thing most worth knowing.

If step 1 fails, stop — the W12-N15 compatibility risk (§5.1) is the likely cause
and no amount of add-on work fixes it.
