"""Kafka transport adapters for publishing and consuming notification events.

Mental model refresher:
- This module is transport glue to Kafka itself.
- It maps Kafka records into the existing consumer-handler adapter flow.
- Business/channel logic still lives in domain/application layers.
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping

from .consumer_handler import handle_message
from .real_senders import send_email_via_mailgun_from_env


def publish_appointment_created_event(
    payload: Mapping[str, Any],
    *,
    topic: str | None = None,
) -> dict[str, Any]:
    """Publish one `appointments.created` event to Kafka."""
    _KafkaConsumer, KafkaProducer, _TopicPartition, _OffsetAndMetadata = _import_kafka_python()
    bootstrap_servers = _bootstrap_servers_from_env()
    topic_name = topic or os.getenv("KAFKA_TOPIC_APPOINTMENTS_CREATED", "appointments.created")
    send_timeout_seconds = float(os.getenv("KAFKA_SEND_TIMEOUT_SECONDS", "10"))

    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=_serialize_json_object,
        acks=os.getenv("KAFKA_PRODUCER_ACKS", "all"),
    )
    try:
        future = producer.send(topic_name, value=dict(payload))
        metadata = future.get(timeout=send_timeout_seconds)
        producer.flush(timeout=send_timeout_seconds)
    finally:
        producer.close()

    return {
        "topic": metadata.topic,
        "partition": metadata.partition,
        "offset": metadata.offset,
    }


def run_email_worker_forever() -> int:
    """Run Kafka consumer loop for email notifications.

    Temporary behavior:
    - By default, this worker forces `notify.sms=false` while toll-free SMS
      verification is pending.
    """
    KafkaConsumer, _KafkaProducer, TopicPartition, OffsetAndMetadata = _import_kafka_python()
    bootstrap_servers = _bootstrap_servers_from_env()
    topic_name = os.getenv("KAFKA_TOPIC_APPOINTMENTS_CREATED", "appointments.created")
    group_id = os.getenv("KAFKA_GROUP_ID", "notifications-email-worker")
    auto_offset_reset = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")
    poll_timeout_ms = _poll_timeout_ms_from_env()
    max_records = int(os.getenv("KAFKA_MAX_RECORDS_PER_POLL", "50"))
    force_sms_disabled = _env_bool("KAFKA_EMAIL_WORKER_FORCE_SMS_DISABLED", default=True)

    consumer = KafkaConsumer(
        topic_name,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset=auto_offset_reset,
    )
    print(
        f"[WORKER START] topic={topic_name} group_id={group_id} "
        f"force_sms_disabled={force_sms_disabled}"
    )

    try:
        while True:
            batches = consumer.poll(timeout_ms=poll_timeout_ms, max_records=max_records)
            if not batches:
                continue

            for _topic_partition, records in batches.items():
                for message in records:
                    message_topic = message.topic
                    message_partition = int(message.partition)
                    message_offset = int(message.offset)

                    try:
                        payload = _deserialize_json_object(message.value)
                    except Exception as exc:
                        print(
                            f"[NO-COMMIT] topic={message_topic} partition={message_partition} "
                            f"offset={message_offset} reason=decode_failed: {exc}"
                        )
                        continue

                    if force_sms_disabled:
                        payload = _with_sms_disabled(payload)

                    internal_record = {
                        "topic": message_topic,
                        "partition": message_partition,
                        "offset": message_offset,
                        "value": payload,
                    }

                    def commit_callback(
                        _record: Mapping[str, Any],
                        *,
                        _topic: str = message_topic,
                        _partition: int = message_partition,
                        _offset: int = message_offset,
                    ) -> None:
                        offsets = {
                            TopicPartition(_topic, _partition): OffsetAndMetadata(_offset + 1, "")
                        }
                        consumer.commit(offsets=offsets)
                        print(
                            f"[COMMIT] topic={_topic} partition={_partition} offset={_offset}"
                        )

                    def reject_callback(
                        _record: Mapping[str, Any],
                        reason: str,
                        *,
                        _topic: str = message_topic,
                        _partition: int = message_partition,
                        _offset: int = message_offset,
                    ) -> None:
                        print(
                            f"[NO-COMMIT] topic={_topic} partition={_partition} "
                            f"offset={_offset} reason={reason}"
                        )

                    result = handle_message(
                        internal_record,
                        send_email=send_email_via_mailgun_from_env,
                        send_sms=_send_sms_noop,
                        commit=commit_callback,
                        reject=reject_callback,
                    )
                    print(
                        f"[RESULT] topic={message_topic} partition={message_partition} "
                        f"offset={message_offset} status={result['status']} "
                        f"should_commit={result['should_commit']} error={result['error']}"
                    )
    except KeyboardInterrupt:
        print("[WORKER STOP] received keyboard interrupt")
        return 0
    except Exception as exc:
        print(f"[WORKER ERROR] {exc}")
        return 1
    finally:
        try:
            consumer.close()
        except Exception:
            pass


def _import_kafka_python() -> tuple[Any, Any, Any, Any]:
    try:
        from kafka import KafkaConsumer, KafkaProducer, TopicPartition
        from kafka.structs import OffsetAndMetadata
    except Exception as exc:
        raise RuntimeError(
            "Kafka support requires `kafka-python`. Install with: pip install kafka-python"
        ) from exc
    return KafkaConsumer, KafkaProducer, TopicPartition, OffsetAndMetadata


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def _bootstrap_servers_from_env() -> list[str]:
    raw = _required_env("KAFKA_BOOTSTRAP_SERVERS")
    servers = [item.strip() for item in raw.split(",") if item.strip()]
    if not servers:
        raise RuntimeError("KAFKA_BOOTSTRAP_SERVERS must include at least one host:port")
    return servers


def _poll_timeout_ms_from_env() -> int:
    timeout_seconds = float(os.getenv("KAFKA_POLL_TIMEOUT_SECONDS", "1.0"))
    timeout_ms = int(timeout_seconds * 1000)
    if timeout_ms <= 0:
        raise RuntimeError("KAFKA_POLL_TIMEOUT_SECONDS must be > 0")
    return timeout_ms


def _serialize_json_object(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _deserialize_json_object(raw: bytes | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)

    if isinstance(raw, bytes):
        text = raw.decode("utf-8")
    elif isinstance(raw, str):
        text = raw
    else:
        raise ValueError(f"Unsupported Kafka payload type: {type(raw).__name__}")

    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Kafka payload must decode to a JSON object")
    return parsed


def _with_sms_disabled(payload: Mapping[str, Any]) -> dict[str, Any]:
    payload_copy: dict[str, Any] = dict(payload)
    notify_raw = payload_copy.get("notify")
    notify = dict(notify_raw) if isinstance(notify_raw, Mapping) else {}
    notify["sms"] = False
    payload_copy["notify"] = notify
    return payload_copy


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"Invalid boolean value for {name}: {raw!r}")


def _send_sms_noop(*, to_phone_e164: str, message: str) -> None:
    """No-op SMS sender used while SMS delivery is temporarily disabled."""
    _ = (to_phone_e164, message)
    return None
