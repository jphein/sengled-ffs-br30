"""Sengled local replacement-cloud server, packaged for Home Assistant.

Runs, in one process:

  1. the SengledTools embedded MQTT broker (amqtt, TLS, anonymous) that bulbs
     connect to;
  2. the SengledTools HTTP server that answers the two endpoints a bulb calls
     on boot -- /life2/device/accessCloud.json and /jbalancer/new/bimqtt -- the
     second of which is what tells the bulb where the MQTT broker lives;
  3. optionally, a relay to Home Assistant's Mosquitto (see bridge.py).

Both server classes are imported from upstream SengledTools rather than
reimplemented, so the wire behaviour cannot drift from the tool used to pair the
bulbs. Upstream is cloned into /opt/sengled-upstream at image build time.

WHY THIS RUNS ON HOME ASSISTANT AND NOT A WORKSTATION
-----------------------------------------------------
`wifi_setup.py` embeds absolute URLs into the bulb during provisioning
(`appServerDomain` / `jbalancerDomain`) and the bulb PERSISTS them. Whatever
address is baked in is called for the rest of the bulb's life. On a segmented
network where the IoT VLAN cannot route to the admin VLAN, a workstation address
would be permanently unreachable -- so the server has to live on an interface
the bulbs can actually reach, and `advertised_host` has to name that interface.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from pathlib import Path

# Upstream package location, populated by the Dockerfile.
UPSTREAM_PATH = os.environ.get("SENGLED_UPSTREAM", "/opt/sengled-upstream")
if UPSTREAM_PATH not in sys.path:
    sys.path.insert(0, UPSTREAM_PATH)

from sengled.http_server import SetupHTTPServer  # noqa: E402
from sengled.mqtt_broker import EmbeddedBroker  # noqa: E402

from bridge import MqttBridge  # noqa: E402

_LOGGER = logging.getLogger("sengled.local")


class ConfigurablePortBroker(EmbeddedBroker):
    """EmbeddedBroker with a settable listen port.

    Upstream hardcodes the bind to `0.0.0.0:{BROKER_TLS_PORT}` (8883) via a
    module constant. 8883 is exactly the port Home Assistant's Mosquitto add-on
    uses for its own TLS listener, so on a host where that is enabled the bulb
    broker must move. Overriding the port here -- rather than monkeypatching the
    upstream constant -- keeps the change local and obvious.

    `_build_config()` is called from EmbeddedBroker.__init__, so the port must be
    assigned BEFORE delegating to super().
    """

    def __init__(self, cert_dir: Path, port: int, **kwargs) -> None:
        self._bind_port = int(port)
        super().__init__(cert_dir, **kwargs)

    def _build_config(self) -> None:  # type: ignore[override]
        super()._build_config()
        self.config["listeners"]["default"]["bind"] = f"0.0.0.0:{self._bind_port}"


def _env_str(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        _LOGGER.warning("%s=%r is not an integer; using %s", name, raw, default)
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean option, recognising false explicitly.

    Falsey values are matched by name rather than by "anything that is not
    truthy", so that a typo warns instead of silently disabling a feature. Empty
    still means "not set, use the default" -- but run.sh must not hand us "" for a
    literal false; see the `get()` comment there for the jq trap that did exactly
    that.
    """
    raw = _env_str(name).lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    _LOGGER.warning("%s=%r is not a boolean; using %s", name, raw, default)
    return default


def main() -> int:
    logging.basicConfig(
        level=getattr(logging, _env_str("LOG_LEVEL", "info").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    advertised_host = _env_str("ADVERTISED_HOST")
    http_port = _env_int("HTTP_PORT", 57542)
    # Default 18883: the Mosquitto add-on already owns host 8883 and 8884.
    mqtt_port = _env_int("MQTT_PORT", 18883)

    if not advertised_host:
        _LOGGER.error(
            "advertised_host is not set. This must be the IP of the Home "
            "Assistant interface that faces the bulbs; it is handed to every "
            "bulb and persisted by it, and cannot be auto-detected from inside "
            "a bridge-networked container. Refusing to start rather than "
            "advertising an address the bulbs cannot reach."
        )
        return 1

    # Certificates live under /share so they survive add-on rebuilds. A bulb that
    # has already connected does not appear to pin them, but regenerating on
    # every restart would be pointless churn.
    cert_dir = Path(_env_str("CERT_DIR", "/share/sengled-local/certs"))
    cert_dir.mkdir(parents=True, exist_ok=True)

    _LOGGER.info("advertising MQTT to bulbs as %s:%s", advertised_host, mqtt_port)
    _LOGGER.info("HTTP endpoints on 0.0.0.0:%s", http_port)

    broker = ConfigurablePortBroker(cert_dir, port=mqtt_port)
    try:
        broker.start()
    except Exception:
        _LOGGER.exception(
            "embedded MQTT broker failed to start on port %s. If Home "
            "Assistant's Mosquitto add-on owns this port, set a different "
            "mqtt_port in the add-on options -- the bulbs are told which port "
            "to use, so any free port works.",
            mqtt_port,
        )
        return 1
    _LOGGER.info("MQTT broker (TLS) listening on 0.0.0.0:%s", mqtt_port)

    # mqtt_host is the value returned in the bimqtt reply -- it must be the
    # address as the BULB sees it, not the container's own address.
    http_server = SetupHTTPServer(
        mqtt_host=advertised_host,
        mqtt_port=mqtt_port,
        preferred_port=http_port,
    )
    if not http_server.start():
        _LOGGER.error("HTTP server failed to start on port %s", http_port)
        broker.stop()
        return 1

    bridge: MqttBridge | None = None
    if _env_bool("BRIDGE_ENABLED", True):
        bridge = MqttBridge(
            bulb_host="127.0.0.1",
            bulb_port=mqtt_port,
            ha_host=_env_str("BRIDGE_HOST", "core-mosquitto"),
            ha_port=_env_int("BRIDGE_PORT", 1883),
            ha_username=_env_str("BRIDGE_USERNAME") or None,
            ha_password=_env_str("BRIDGE_PASSWORD") or None,
        )
        bridge.start()
    else:
        _LOGGER.info("MQTT bridge disabled; bulb telemetry stays inside this add-on")

    stop_event = threading.Event()

    def _handle_signal(signum, _frame) -> None:
        _LOGGER.info("received signal %s, shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    _LOGGER.info("ready -- waiting for bulbs")
    try:
        while not stop_event.is_set():
            stop_event.wait(1.0)
    finally:
        if bridge is not None:
            bridge.stop()
        http_server.stop()
        broker.stop()
        _LOGGER.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
