# `firmware/` — local artifacts (mostly git-ignored)

> ### 🛈 You almost certainly don't need this directory
> The recommended path — [Path 1](../README.md#path-1--solderless-local-control-recommended) —
> involves **no flashing at all**. The bulb keeps its stock firmware and you control it over UDP.
>
> This directory only matters on [Path 3](../README.md#path-3--solderless-ota-flash) (solderless
> OTA, ESP8266/WF863 only — **not this bulb**) or
> [Path 4](../README.md#path-4--uart-flash-to-open-firmware) (wired UART, advanced).

Almost everything that lands here is deliberately excluded by [`../.gitignore`](../.gitignore) and
**must never be committed**.

## What goes here

| File | Committed? | Why |
|---|---|---|
| `*-stock.bin` — full flash dump, read **before** you write anything | ❌ **no** (`*.bin`) | Large; contains the bulb's provisioned WiFi credentials, device keys, and MAC. Publishing one leaks your network. |
| `*_backup*` — any read-back image | ❌ **no** (`*_backup*`) | Same. |
| `secrets.yaml` | ❌ **no** | Real SSID / WiFi password / API + OTA keys. |
| `*.yaml` — per-bulb firmware config | ✅ **yes**, once sanitized | Useful to others — **only** with `!secret` references, never inline credentials. |
| Verified GPIO / channel maps | ✅ **yes** | Hardware facts, not secrets — and genuinely new information for this bulb. |

## Take a backup first. Always.

The stock image is your **only** way back to working vendor firmware.

**Path 3 (solderless OTA, ESP8266 only):** the `Sengled-Rescue` web UI at `http://192.168.4.1` does
this for you — choose *full → backup selected* **before** you flash anything. Save the download here.

**Path 4 (wired UART, RTL8710BN):** read it yourself first. There is no vendor image to
re-download.

```bash
# RTL8710BN / MX1290 — ltchiptool, NOT esptool.py
ltchiptool flash read --family realtek-ambz firmware/sengled-w12n15-stock.bin
```

Verify the dump is plausible before trusting it — a file of all `0xFF` means the read failed:

```bash
ls -l firmware/sengled-w12n15-stock.bin    # expect ~2 MiB for WF864
md5sum firmware/sengled-w12n15-stock.bin   # record this somewhere off-device
```

Store backups **outside the repo** — an external drive or your password manager's file attachments.
Do not rely on `.gitignore` alone as your safety net.

## Secrets template

Create `firmware/secrets.yaml` locally (git-ignored) from this shape:

```yaml
wifi_ssid: "YOUR_WIFI_SSID"
wifi_password: "YOUR_WIFI_PASSWORD"
api_key: "GENERATE_A_32_BYTE_BASE64_KEY"
ota_password: "YOUR_OTA_PASSWORD"
```

Generate an ESPHome API encryption key with:

```bash
openssl rand -base64 32
```

## Before you commit anything from this directory

```bash
grep -rInE 'ssid:|password:|token|bearer|[0-9a-f]{2}(:[0-9a-f]{2}){5}' firmware/
```

Every hit must be a `!secret` reference or a `YOUR_*` placeholder. If it is a real value, **do not
commit — and if it is already staged, amend it out rather than fixing it forward.**
