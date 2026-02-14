#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${KAFKA_CONTAINER_NAME:-kafka-local}"

if ! docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "[INFO] Kafka container not found: ${CONTAINER_NAME}"
  exit 0
fi

echo "[CONTAINER]"
docker ps -a --filter "name=^/${CONTAINER_NAME}$" --format 'name={{.Names}} status={{.Status}} ports={{.Ports}}'

if docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo ""
  echo "[TOPICS]"
  docker exec "${CONTAINER_NAME}" /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --list | sed 's/^/- /'
fi
