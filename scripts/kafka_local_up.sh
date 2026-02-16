#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${KAFKA_CONTAINER_NAME:-kafka-local}"
IMAGE="${KAFKA_IMAGE:-apache/kafka:3.9.0}"
TOPIC="${KAFKA_TOPIC_APPOINTMENTS_CREATED:-appointments.created}"
DLQ_TOPIC="${KAFKA_TOPIC_APPOINTMENTS_CREATED_DLQ:-${TOPIC}.dlq}"
HOST_PORT="${KAFKA_PORT:-9092}"

if docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "[INFO] Kafka container already running: ${CONTAINER_NAME}"
elif docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "[INFO] Starting existing Kafka container: ${CONTAINER_NAME}"
  docker start "${CONTAINER_NAME}" >/dev/null
else
  echo "[INFO] Creating Kafka container: ${CONTAINER_NAME}"
  docker run -d \
    --name "${CONTAINER_NAME}" \
    -p "${HOST_PORT}:9092" \
    "${IMAGE}" >/dev/null
fi

echo "[INFO] Waiting for broker readiness..."
ready="false"
for i in $(seq 1 90); do
  if docker exec "${CONTAINER_NAME}" /bin/bash -lc \
    "timeout 3 /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1"; then
    ready="true"
    break
  fi
  sleep 1
done

if [[ "${ready}" != "true" ]]; then
  echo "[ERROR] Kafka broker did not become ready in time."
  echo "[INFO] Check logs: docker logs ${CONTAINER_NAME}"
  exit 1
fi

echo "[INFO] Ensuring topic exists: ${TOPIC}"
docker exec "${CONTAINER_NAME}" /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --if-not-exists \
  --topic "${TOPIC}" \
  --partitions 1 \
  --replication-factor 1 >/dev/null

echo "[INFO] Ensuring DLQ topic exists: ${DLQ_TOPIC}"
docker exec "${CONTAINER_NAME}" /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --if-not-exists \
  --topic "${DLQ_TOPIC}" \
  --partitions 1 \
  --replication-factor 1 >/dev/null

docker exec "${CONTAINER_NAME}" /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic "${TOPIC}"

docker exec "${CONTAINER_NAME}" /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic "${DLQ_TOPIC}"

echo "[OK] Kafka is ready at localhost:${HOST_PORT}"
