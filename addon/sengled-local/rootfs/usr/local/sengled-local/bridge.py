"""Relay between the bulb-facing embedded broker and Home Assistant's Mosquitto.

Why a relay and not a broker bridge: the bulb-facing broker is `amqtt`, which has
no bridging feature of its own (unlike Mosquitto). So we run two ordinary MQTT
clients back to back.

    bulbs --TLS--> amqtt (this add-on) <== relay ==> Mosquitto (HA) <--> HA

LOOP PREVENTION, and why it is structural rather than stateful
--------------------------------------------------------------
The obvious wiring -- subscribe `wifielement/#` on both sides and cross-publish --
ping-pongs forever: HA publishes `wifielement/X/update`, the bulb-side client is
subscribed to `#` so it echoes upstream, the HA-side client is subscribed to
`.../update` so it echoes back down, ad infinitum.

Rather than deduplicate messages (stateful, and fragile with retained/QoS1
redelivery), the two directions are given provably disjoint topic sets:

    upstream   (bulbs -> HA): everything under wifielement/# EXCEPT */update
    downstream (HA -> bulbs): only wifielement/+/update

Since no topic is eligible in both directions, a message physically cannot make
a round trip. The cost is that HA cannot observe its own published commands
echoed back -- which is no loss, because HA is the one that published them.
"""

from __future__ import annotations

import logging
import ssl
import threading
from typing import Any

import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger("sengled.bridge")

# Bulb -> HA: forwarded upstream. Bulbs publish status/telemetry here.
UPSTREAM_SUBSCRIPTION = "wifielement/#"
# Bulb <- HA: forwarded downstream. This is the control topic.
DOWNSTREAM_SUBSCRIPTION = "wifielement/+/update"
# Topic suffix that is downstream-only. Never relayed upstream (see module docs).
DOWNSTREAM_ONLY_SUFFIX = "/update"


def _make_client(client_id: str) -> mqtt.Client:
    """Build a paho client that behaves the same on paho-mqtt 1.x and 2.x.

    paho 2.0 made the callback API version a required first positional argument.
    Asking explicitly for VERSION1 keeps the legacy callback signatures used
    below valid under both major versions.
    """
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
    except (AttributeError, TypeError):
        return mqtt.Client(client_id=client_id)


class MqttBridge:
    """Bidirectional relay with structurally disjoint directions."""

    def __init__(
        self,
        bulb_host: str,
        bulb_port: int,
        ha_host: str,
        ha_port: int,
        ha_username: str | None = None,
        ha_password: str | None = None,
    ) -> None:
        self._bulb_host = bulb_host
        self._bulb_port = bulb_port
        self._ha_host = ha_host
        self._ha_port = ha_port

        self._bulb = _make_client("sengled-local-bridge-bulbside")
        self._ha = _make_client("sengled-local-bridge-haside")

        if ha_username:
            self._ha.username_pw_set(ha_username, ha_password or None)

        # The embedded broker presents a self-signed certificate from a CA it
        # generated itself, so there is nothing meaningful to verify against.
        # (The bulbs cannot be verifying it either -- which is precisely why a
        # locally generated CA works on them at all.)
        self._bulb.tls_set(cert_reqs=ssl.CERT_NONE)
        self._bulb.tls_insecure_set(True)

        self._bulb.on_connect = self._on_bulb_connect
        self._bulb.on_message = self._on_bulb_message
        self._ha.on_connect = self._on_ha_connect
        self._ha.on_message = self._on_ha_message

        self._stop = threading.Event()

    # ------------------------------------------------------------------
    # bulb side (upstream: bulbs -> HA)
    # ------------------------------------------------------------------
    def _on_bulb_connect(self, client, userdata, flags, rc, *args) -> None:
        if rc != 0:
            _LOGGER.error("bulb-side broker connect failed (rc=%s)", rc)
            return
        client.subscribe(UPSTREAM_SUBSCRIPTION, qos=1)
        _LOGGER.info(
            "bulb side connected to %s:%s, subscribed %s",
            self._bulb_host,
            self._bulb_port,
            UPSTREAM_SUBSCRIPTION,
        )

    def _on_bulb_message(self, client, userdata, msg: Any) -> None:
        # THE loop breaker. Do not remove without re-reading the module docstring.
        if msg.topic.endswith(DOWNSTREAM_ONLY_SUFFIX):
            return
        try:
            self._ha.publish(msg.topic, msg.payload, qos=1)
        except Exception:  # noqa: BLE001 - a relay must never die on one message
            _LOGGER.exception("failed to relay upstream: %s", msg.topic)

    # ------------------------------------------------------------------
    # HA side (downstream: HA -> bulbs)
    # ------------------------------------------------------------------
    def _on_ha_connect(self, client, userdata, flags, rc, *args) -> None:
        if rc != 0:
            _LOGGER.error("HA broker connect failed (rc=%s)", rc)
            return
        client.subscribe(DOWNSTREAM_SUBSCRIPTION, qos=1)
        _LOGGER.info(
            "HA side connected to %s:%s, subscribed %s",
            self._ha_host,
            self._ha_port,
            DOWNSTREAM_SUBSCRIPTION,
        )

    def _on_ha_message(self, client, userdata, msg: Any) -> None:
        try:
            self._bulb.publish(msg.topic, msg.payload, qos=1)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("failed to relay downstream: %s", msg.topic)

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Connect both sides and service them on background threads."""
        # connect_async + loop_start so a broker that is not up yet does not
        # block add-on start-up; paho retries on its own.
        self._bulb.connect_async(self._bulb_host, self._bulb_port, keepalive=60)
        self._bulb.loop_start()
        self._ha.connect_async(self._ha_host, self._ha_port, keepalive=60)
        self._ha.loop_start()
        _LOGGER.info("bridge started")

    def stop(self) -> None:
        self._stop.set()
        for client, label in ((self._bulb, "bulb"), (self._ha, "HA")):
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("error stopping %s side", label, exc_info=True)
        _LOGGER.info("bridge stopped")
