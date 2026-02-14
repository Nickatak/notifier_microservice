#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${KAFKA_CONTAINER_NAME:-kafka-local}"

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  docker rm -f "${CONTAINER_NAME}" >/dev/null
  echo "[OK] Removed Kafka container: ${CONTAINER_NAME}"
else
  echo "[INFO] Kafka container not found: ${CONTAINER_NAME}"
fi
