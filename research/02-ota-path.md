# OTA (No-Solder) Reflash Path — "FFS / Sengled" BR30 RGBCW WiFi Bulb (ASIN B097CYHRZJ)

**Status:** IN PROGRESS (started 2026-08-09)
**Sourcing:** compiled from FCC records, upstream project docs, and community tooling matrices.
**Question:** Can these 8 bulbs be flashed with open firmware over-the-air, without soldering UART?

## Verdict

_(to be filled — see bottom)_

---

## Working notes

### F1. tuya-cloudcutter does NOT support ESP8266/ESP8285 — chip identity is decisive

Verified from the upstream README and LibreTiny docs:

- Supported chips: **Beken BK7231T, BK7231N** (unpatched), **Realtek RTL8710BN** (unpatched,
  SDK 2.0.0 excluded), **RTL8720CF** (unpatched, caveats).
- **Explicitly NOT supported: ESP8266, ESP8285, or other chipsets.**
- LibreTiny doc is blunter still: *"This currently applies to BK7231T and BK7231N only.
  `tuya-cloudcutter` can't be used for other chips."*

=> If the parallel chip-ID agent finds an **ESP8285**, cloudcutter is off the table by
construction, not by firmware version.

### F2. Cloudcutter is defeated by patched Tuya SDK (Feb 2022+)

- README: *"Tuya has patched their SDK as of February 2022. Any device with firmware compiled
  against a patched SDK will not be exploitable."*
- Known-patched BK7231N firmware versions listed on the wiki include 1.1.2, 1.1.12, 1.1.15,
  1.3.3, 1.3.8, 1.3.10, 1.5.10, 2.0.15.
- A bulb bought in the B097CYHRZJ era (listing live ~2021) *could* predate the patch, but
  only matters if the chip is Beken at all.

### F3. Cloudcutter host/adapter requirements (for completeness)

- Linux host with **NetworkManager + Docker + sudo**. Uses `nmcli` to bring up an AP.
- README asks for "a stand-alone wifi adapter" that is **not** your primary networking path
  (Ethernet preferred for internet). It does **not** publish a chipset allow/deny list in the
  README itself — needs the INSTRUCTIONS.md / wiki for hard adapter guidance. (chasing)

### F4. *** The bulb is very likely GENUINE Sengled, not rebadged Tuya ***

- Amazon `B097CYHRZJ` title: *"**Sengled** Smart Light Bulbs, Updated FFS Smart Bulb That
  Work With Alexa, Google, Smart Recessed Light Bulbs 65W Equivalent, 7.5W, Color Changing
  Light Bulb, 2.4GHz WiFi Only, No Hub Required, 2 Pack"* — brand field **Sengled**.
- "FFS" is not a separate brand; it is a keyword inside Sengled's own Amazon titles. Sibling
  ASIN `B097CZ49V8` = *"Sengled BR30 Smart Light Bulb, Updated FFS WiFi Led Flood Light
  Bulbs..."* (same family, white version). Both are Sengled listings.
- Sengled runs **its own cloud**, not Tuya's. Sengled WiFi bulbs pair with the *Sengled Home*
  app and talk MQTT to Sengled servers — they are **not** Smart Life / Tuya devices.
- Known Sengled WiFi hardware: **W31-N15 RGBW bulb = ESP8266**, and the Tasmota template for
  it lists flashing method **"USB to Serial"** (i.e. wired), with the note *"Programming pins
  hidden behind capacitors, you may need to fully remove module to flash"*. No OTA path.

=> Genuine Sengled => no Tuya firmware => **no tuya-cloudcutter, no tuya-convert.** Those
exploits target Tuya's SDK specifically; they have nothing to attack here.

### F5. *** Sengled's cloud is DEAD (2025) — and that opened a LOCAL path ***

- June 18 2025: Sengled's cloud went down hard; WiFi bulbs stopped responding via app, Alexa
  and Google. Outages recurred through July 2025.
- Aug 1 2025: **Amazon permanently discontinued the Sengled Alexa skill**, citing "repeated
  extended service interruptions."
- Sengled reportedly in financial crisis — staff unpaid since Jan 2025, strikes by Apr 2025.

This is why the vendor app is unusable — it is not a user problem, the backend is gone.

- **`FalconFour/ha-sengled-local`** — HA integration + add-on that stands up a **local
  replacement Sengled server** (MQTT). README: *"brings your Sengled smart bulbs back to life
  after Sengled shut down their cloud servers."* Supports **"All WiFi Sengled Bulbs"**, and
  **only** the "No Hub Required" WiFi models — which is exactly what B097CYHRZJ is.
- Pairing is done by a companion tool, **SengledTools**, which must be pointed at the add-on's
  `/bimqtt` and `accessCloud.json` URLs instead of Sengled's.

=> Candidate answer: **don't reflash at all.** Re-point the stock firmware at a local server.
(verifying SengledTools onboarding next)
