# Changelog

## 0.1.3

- **FIX: `bridge_enabled: false` was starting the bridge anyway.** `run.sh`'s
  option reader used jq's `.[$k] // ""`, but `//` is jq's *alternative* operator
  and fires on `false` as well as `null` -- so a literal `false` arrived as `""`,
  which `_env_bool` read as "unset, use the default" (True). Result: the bridge
  ran when disabled and filled the log with `HA broker connect failed (rc=5)`.
  Now uses `if has($k) and .[$k] != null then .[$k] else "" end`, which keeps
  boolean `false` intact while still mapping missing/null to `""`.
- `_env_bool` now recognises `0/false/no/off` explicitly and warns on an
  unrecognised value instead of silently treating it as false.
- Docs: corrected a wrong claim that `advertised_host` is persisted by the bulb.
  It is not -- the provisioning payload carries only `appServerDomain`,
  `jbalancerDomain`, `timeZone` and `routerInfo`, so the MQTT address is
  re-fetched from bimqtt on every boot. Changing `advertised_host` or `mqtt_port`
  needs a bulb **reboot**, not a re-pair.
- Verified (no code change needed): the bimqtt reply hands bulbs
  `advertised_host:18883`, matching the broker's actual bind.

## 0.1.0

Initial release. Not yet validated against a live bulb.

- HTTP endpoints `/life2/device/accessCloud.json` and `/jbalancer/new/bimqtt`,
  served by upstream SengledTools' `SetupHTTPServer`.
- Embedded `amqtt` TLS broker for bulb connections on a configurable port,
  defaulting to **18883**: upstream hardcodes 8883, but the official Mosquitto
  add-on binds 1883/1884/8883/8884, so both conventional TLS-MQTT ports are
  already taken on a typical HA host.
- Optional loop-safe relay to Home Assistant's Mosquitto.
- `advertised_host` is mandatory: bulbs persist the address given at pairing
  time, so the add-on refuses to start rather than advertise a wrong one.
