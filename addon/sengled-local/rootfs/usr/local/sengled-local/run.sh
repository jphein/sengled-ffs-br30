#!/usr/bin/env bash
# shellcheck shell=bash
# Read add-on options DIRECTLY from /data/options.json (which Supervisor always
# writes before starting the container) and hand them to server.py as env vars.
#
# We deliberately do NOT use bashio::config here. On this Supervisor, bashio's
# config lookup goes through the Supervisor API and is denied ("Unable to access
# the API, forbidden") even with `hassio_api: true` set and a rebuild done -- so
# every option came back empty and the add-on FATAL'd on a wrongly-"empty"
# advertised_host that the user had actually set. Reading options.json needs no
# API access and no special permission.

set -euo pipefail

OPTIONS=/data/options.json

if [ ! -f "${OPTIONS}" ]; then
    echo "[sengled-local] FATAL: ${OPTIONS} not found -- Supervisor did not write add-on options." >&2
    exit 1
fi

# jq is present in the HA base image (bashio depends on it).
#
# Do NOT use `.[$k] // ""` here. jq's `//` is the *alternative* operator, not a
# null-coalesce: it fires on `false` as well as `null`. That silently turned
# `bridge_enabled: false` into "", which server.py's _env_bool then read as
# "unset, use the default" -- i.e. True -- so disabling the bridge enabled it,
# and the log filled with "HA broker connect failed (rc=5)".
#
# has() + an explicit null test keeps boolean false intact while still mapping a
# missing or null option to "".
get() {
    jq -r --arg k "$1" 'if has($k) and .[$k] != null then .[$k] else "" end' "${OPTIONS}"
}

ADVERTISED_HOST="$(get advertised_host)"
HTTP_PORT="$(get http_port)"
MQTT_PORT="$(get mqtt_port)"
BRIDGE_ENABLED="$(get bridge_enabled)"
BRIDGE_HOST="$(get bridge_host)"
BRIDGE_PORT="$(get bridge_port)"
BRIDGE_USERNAME="$(get bridge_username)"
BRIDGE_PASSWORD="$(get bridge_password)"
LOG_LEVEL="$(get log_level)"

if [ -z "${ADVERTISED_HOST}" ]; then
    echo "[sengled-local] FATAL: advertised_host is empty." >&2
    echo "[sengled-local] Set it in the add-on Configuration tab to the IP of the" >&2
    echo "[sengled-local] Home Assistant interface that faces your bulbs' network." >&2
    # Keys only (never values) -- tells us if options.json is empty vs populated,
    # without printing the bridge password.
    echo "[sengled-local] keys present in options.json: $(jq -rc 'keys' "${OPTIONS}" 2>/dev/null)" >&2
    exit 1
fi

echo "[sengled-local] Sengled Local Server starting"
echo "[sengled-local]   advertising to bulbs as: ${ADVERTISED_HOST}"
echo "[sengled-local]   HTTP endpoints port:     ${HTTP_PORT}"
echo "[sengled-local]   MQTT (TLS) port:         ${MQTT_PORT}"
echo "[sengled-local]   bridge to HA broker:     ${BRIDGE_ENABLED} (${BRIDGE_HOST}:${BRIDGE_PORT})"

export ADVERTISED_HOST HTTP_PORT MQTT_PORT
export BRIDGE_ENABLED BRIDGE_HOST BRIDGE_PORT BRIDGE_USERNAME BRIDGE_PASSWORD
export LOG_LEVEL
export SENGLED_UPSTREAM="/opt/sengled-upstream"
export CERT_DIR="/share/sengled-local/certs"
export PYTHONUNBUFFERED=1

cd /usr/local/sengled-local
exec python3 server.py
