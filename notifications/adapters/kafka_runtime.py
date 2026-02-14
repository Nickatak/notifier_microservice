"""Kafka transport adapters for publishing and consuming notification events.

Mental model refresher:
- This module is transport glue to Kafka itself.
- It maps Kafka records into the existing consumer-handler adapter flow.
- Business/channel logic still lives in domain/application layers.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
    KafkaConsumer, KafkaProducer, TopicPartition, OffsetAndMetadata = _import_kafka_python()
    bootstrap_servers = _bootstrap_servers_from_env()
    topic_name = os.getenv("KAFKA_TOPIC_APPOINTMENTS_CREATED", "appointments.created")
    dlq_enabled = _env_bool("KAFKA_DLQ_ENABLED", default=True)
    dlq_topic = os.getenv("KAFKA_TOPIC_APPOINTMENTS_CREATED_DLQ", f"{topic_name}.dlq")
    group_id = os.getenv("KAFKA_GROUP_ID", "notifications-email-worker")
    auto_offset_reset = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")
    poll_timeout_ms = _poll_timeout_ms_from_env()
    max_records = int(os.getenv("KAFKA_MAX_RECORDS_PER_POLL", "50"))
    dlq_send_timeout_seconds = float(
        os.getenv(
            "KAFKA_DLQ_SEND_TIMEOUT_SECONDS",
            os.getenv("KAFKA_SEND_TIMEOUT_SECONDS", "10"),
        )
    )
    force_sms_disabled = _env_bool("KAFKA_EMAIL_WORKER_FORCE_SMS_DISABLED", default=True)

    consumer = KafkaConsumer(
        topic_name,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset=auto_offset_reset,
    )
    dlq_producer = (
        KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=_serialize_json_object,
            acks=os.getenv("KAFKA_PRODUCER_ACKS", "all"),
        )
        if dlq_enabled
        else None
    )
    print(
        f"[WORKER START] topic={topic_name} group_id={group_id} "
        f"force_sms_disabled={force_sms_disabled} "
        f"dlq_enabled={dlq_enabled} dlq_topic={dlq_topic}"
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

                    def commit_current_offset() -> None:
                        offsets = {
                            TopicPartition(message_topic, message_partition): _offset_and_metadata(
                                OffsetAndMetadata, message_offset + 1
                            )
                        }
                        consumer.commit(offsets=offsets)
                        print(
                            "[COMMIT] "
                            f"topic={message_topic} partition={message_partition} "
                            f"offset={message_offset}"
                        )

                    def publish_to_dlq(*, reason: str, source_payload: Any) -> bool:
                        if dlq_producer is None:
                            return False

                        dlq_payload = _build_dlq_payload(
                            source_topic=message_topic,
                            source_partition=message_partition,
                            source_offset=message_offset,
                            source_payload=source_payload,
                            failure_reason=reason,
                        )
                        try:
                            future = dlq_producer.send(dlq_topic, value=dlq_payload)
                            metadata = future.get(timeout=dlq_send_timeout_seconds)
                        except Exception as exc:
                            print(
                                "[DLQ ERROR] "
                                f"source_topic={message_topic} source_partition={message_partition} "
                                f"source_offset={message_offset} reason={reason} error={exc}"
                            )
                            return False

                        print(
                            "[DLQ] "
                            f"source_topic={message_topic} source_partition={message_partition} "
                            f"source_offset={message_offset} dlq_topic={metadata.topic} "
                            f"dlq_partition={metadata.partition} dlq_offset={metadata.offset} "
                            f"reason={reason}"
                        )
                        return True

                    try:
                        payload = _deserialize_json_object(message.value)
                    except Exception as exc:
                        reason = f"decode_failed: {exc}"
                        if publish_to_dlq(reason=reason, source_payload=message.value):
                            commit_current_offset()
                        else:
                            print(
                                f"[NO-COMMIT] topic={message_topic} partition={message_partition} "
                                f"offset={message_offset} reason={reason}"
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
                    ) -> None:
                        _ = _record
                        commit_current_offset()

                    def reject_callback(
                        _record: Mapping[str, Any],
                        reason: str,
                    ) -> None:
                        source_payload = _record.get("value")
                        if publish_to_dlq(reason=reason, source_payload=source_payload):
                            commit_current_offset()
                        else:
                            print(
                                f"[NO-COMMIT] topic={message_topic} partition={message_partition} "
                                f"offset={message_offset} reason={reason}"
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
        if dlq_producer is not None:
            try:
                dlq_producer.flush(timeout=dlq_send_timeout_seconds)
            except Exception:
                pass
            try:
                dlq_producer.close()
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


def _build_dlq_payload(
    *,
    source_topic: str,
    source_partition: int,
    source_offset: int,
    source_payload: Any,
    failure_reason: str,
) -> dict[str, Any]:
    payload = {
        "event_type": f"{source_topic}.dlq",
        "failed_at": datetime.now(tz=UTC).isoformat(),
        "failure_reason": failure_reason,
        "source": {
            "topic": source_topic,
            "partition": source_partition,
            "offset": source_offset,
        },
        "payload": _to_json_compatible(source_payload),
    }

    if isinstance(source_payload, Mapping):
        event_id = source_payload.get("event_id")
        if isinstance(event_id, str) and event_id.strip():
            payload["source_event_id"] = event_id.strip()

    return payload


def _to_json_compatible(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_compatible(item) for item in value]
    return repr(value)


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


def _offset_and_metadata(offset_and_metadata_type: Any, offset: int) -> Any:
    """Build kafka-python OffsetAndMetadata across version signatures."""
    try:
        return offset_and_metadata_type(offset, "", -1)
    except TypeError:
        try:
            return offset_and_metadata_type(offset, "", None)
        except TypeError:
            return offset_and_metadata_type(offset, "")
