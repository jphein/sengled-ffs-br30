# Firmware + Home Assistant End-State — FFS/Sengled BR30 RGBCW (ASIN B097CYHRZJ)

**Status:** IN PROGRESS (started 2026-08-09 21:05 PDT)
**Sourcing:** compiled from FCC records, upstream project docs, and community tooling matrices.
**Scope:** which firmware per chip type, ready-to-adapt ESPHome RGBCW yaml, what HA sees, how to replicate across 8.

## Reference environment

- Home Assistant OS, Mosquitto MQTT broker already configured
- ESPHome tooling present: local `esphome` CLI compile + dashboard at `esphome.local`
- 8 bulbs to convert
- Chip unknown as of writing (confirmation in progress) — note: later findings in
  `01-chip-id.md` supersede this line. The Beken/ESP8285 guess was wrong; Sengled uses its own
  in-house modules (ESP8266EX on WF863, MXCHIP elsewhere).

## Working notes

(appended as research proceeds)
