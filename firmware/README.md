# `firmware/` — local artifacts (mostly git-ignored)

This directory is where **your** device-specific files live. Almost everything that lands here is
deliberately excluded by [`../.gitignore`](../.gitignore) and **must never be committed**.

## What goes here

| File | Committed? | Why |
|---|---|---|
| `*-stock.bin` — full stock flash dump, read **before** you write anything | ❌ **no** (`*.bin`) | Large; contains the bulb's provisioned WiFi credentials, device keys, and MAC. Publishing one leaks your network. |
| `*_backup*` — any read-back image | ❌ **no** (`*_backup*`) | Same. |
| `secrets.yaml` — ESPHome secrets | ❌ **no** | Real SSID / WiFi password / API + OTA keys. |
| `bulb-br30-NN.yaml` — per-bulb ESPHome config | ✅ **yes**, once sanitized | Useful to others — **only** with `!secret` references, never inline credentials. |
| `*.tasmota.json` — verified Tasmota templates | ✅ **yes** | GPIO maps are hardware facts, not secrets. |

## Take a backup first. Always.

The stock image is your **only** way back to a working vendor firmware. Read it before you write
anything:

```bash
esptool.py --port /dev/ttyUSB0 --baud 115200 \
  read_flash 0x0 0x400000 firmware/sengled-br30-stock.bin
```

Verify the dump is plausible before trusting it — a 4 MB file of `0xFF` means the read failed:

```bash
ls -l firmware/sengled-br30-stock.bin      # expect ~4 MiB (4194304 bytes)
md5sum firmware/sengled-br30-stock.bin     # record this somewhere off-device
```

Store backups **outside the repo** — an external drive or your password manager's file
attachments. Do not rely on `.gitignore` alone as your safety net.

## Secrets template

Create `firmware/secrets.yaml` locally (git-ignored) from this shape:

```yaml
wifi_ssid: "YOUR_WIFI_SSID"
wifi_password: "YOUR_WIFI_PASSWORD"
api_key: "GENERATE_A_32_BYTE_BASE64_KEY"
ota_password: "YOUR_OTA_PASSWORD"
```

Generate the ESPHome API encryption key with:

```bash
openssl rand -base64 32
```

## Before you commit anything from this directory

```bash
grep -rInE 'ssid:|password:|token|bearer|[0-9a-f]{2}(:[0-9a-f]{2}){5}' firmware/
```

Every hit must be a `!secret` reference or a `YOUR_*` placeholder. If it is a real value, **do not
commit — and if it is already staged, amend it out rather than fixing it forward.**
