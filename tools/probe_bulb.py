#!/usr/bin/env python3
"""
Identify a Sengled Wi-Fi bulb over UDP — no pairing, no flashing, no teardown.

Protocol is plain unauthenticated JSON over UDP/9080 (verified in SengledTools
sengled/udp.py: send_udp_command -> sendto((bulb_ip, 9080))).

USAGE
  Bulb in SoftAP mode (factory reset: flick power 5+ times):
      join the open AP "Sengled_Wi-Fi Bulb_XXXX", then:
      ./probe_bulb.py                      # defaults to 192.168.8.1
  Bulb already paired onto the LAN:
      ./probe_bulb.py <bulb-ip>

WHAT IT TELLS YOU
  get_software_version -> version string embedding the model, e.g. "..._W12-N15_SYSTEM_..."
  search_devices       -> presence of R/G/B keys => RGB-capable vs white-only

  Model W31-N15 / W31-N11  => WF863 / ESP8266EX => solderless OTA flash SUPPORTED
  Anything else (W12-*, W21-*, W11-*) => WF864/MX1290 or EMW3091 => NOT flashable;
                                          local control still fully works.
"""

import json
import re
import socket
import sys

PORT = 9080
QUERIES = [
    ("get_device_mac", {"func": "get_device_mac", "param": {}}),
    ("get_software_version", {"func": "get_software_version", "param": {}}),
    ("get_device_mode", {"func": "get_device_mode", "param": {}}),
    ("search_devices", {"func": "search_devices", "param": {}}),
]


def ask(ip: str, payload: dict, timeout: float = 3.0):
    """Send one JSON UDP command and return the parsed reply, or None."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.sendto(json.dumps(payload).encode(), (ip, PORT))
            data, _ = s.recvfrom(4096)
        return json.loads(data.decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None


def main() -> int:
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.8.1"
    print(f"Probing Sengled bulb at {ip}:{PORT} ...\n")

    answered = False
    model = None
    result_of = {}

    for name, payload in QUERIES:
        resp = ask(ip, payload)
        if resp is None:
            print(f"  [--] {name}: no response")
            continue
        answered = True
        res = resp.get("result", resp)
        result_of[name] = res
        print(f"  [ok] {name}: {json.dumps(res)[:300]}")

    if not answered:
        print(
            "\nNo reply. Check that you are joined to the bulb's own AP "
            '("Sengled_Wi-Fi Bulb_XXXX") for 192.168.8.1, or that you passed the\n'
            "bulb's LAN IP. UDP/9080 must not be firewalled or on another VLAN."
        )
        return 1

    version = (result_of.get("get_software_version") or {}).get("version", "")
    if isinstance(version, str):
        m = re.search(r"_(W\d{2}-[A-Z]\d{2})_", version)
        if m:
            model = m.group(1)

    sd = result_of.get("search_devices") or {}
    is_rgb = all(k in sd for k in ("R", "G", "B")) if isinstance(sd, dict) else False

    print("\n--- VERDICT ---")
    print(f"Model:   {model or 'UNKNOWN (version string did not match _Wxx-Nxx_)'}")
    print(f"Colour:  {'RGB-capable' if is_rgb else 'white-only / undetermined'}")
    if model in {"W31-N15", "W31-N11"}:
        print("Flash:   SUPPORTED -- WF863 / ESP8266EX. Solderless OTA to "
              "Tasmota/ESPHome/WLED is available.")
    elif model:
        print("Flash:   NOT SUPPORTED -- non-ESP8266 module (WF864/MX1290 or EMW3091).")
        print("         Do NOT use --force-flash: the shim is ESP8266 machine code.")
        print("         Local control (UDP/MQTT + Home Assistant) still works fully.")
    else:
        print("Flash:   UNDETERMINED -- read the FCC ID on the bulb instead "
              "(2AGN8-WF863 = flashable; 2AGN8-WF864/WF862 = not).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
