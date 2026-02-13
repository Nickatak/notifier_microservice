"""Consumer-handler adapter functions (Kafka-like flow without Kafka).

Mental model refresher:
- This is the controller-like entrypoint for event processing.
- Real Kafka code would call this after polling a record.
- Flow:
  record -> parse adapter -> application use-case -> commit/no-commit decision
- This module owns transport lifecycle behavior (parse errors, commit callbacks),
  not channel business rules.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from ..application.process import process_notification_event
from ..types import EventDict, SendEmailFn, SendSMSFn
from .payload import parse_event_payload

Record = Mapping[str, Any]
CommitFn = Callable[[Record], None]
RejectFn = Callable[[Record, str], None]


def handle_message(
    record: Record,
    *,
    send_email: SendEmailFn,
    send_sms: SendSMSFn,
    commit: CommitFn,
    reject: RejectFn | None = None,
) -> dict[str, Any]:
    """Handle one incoming record and decide commit/no-commit.

    Commit policy in this demo:
    - Commit only when all requested channels succeed.
    - Do not commit on parse failures or channel failures.
    """
    try:
        payload = _get_record_payload(record)
        event = parse_event_payload(payload)
    except Exception as exc:
        error = f"parse_failed: {exc}"
        if reject is not None:
            reject(record, error)
        return {
            "status": "parse_failed",
            "record_meta": _record_meta(record),
            "event": None,
            "processing": None,
            "should_commit": False,
            "error": error,
        }

    processing = process_notification_event(event, send_email=send_email, send_sms=send_sms)
    should_commit = bool(processing["all_requested_succeeded"])

    if should_commit:
        commit(record)
        status = "processed_and_committed"
        error = None
    else:
        status = "processed_not_committed"
        error = "one_or_more_requested_channels_failed"
        if reject is not None:
            reject(record, error)

    return {
        "status": status,
        "record_meta": _record_meta(record),
        "event": event,
        "processing": processing,
        "should_commit": should_commit,
        "error": error,
    }


def handle_batch(
    records: Sequence[Record],
    *,
    send_email: SendEmailFn,
    send_sms: SendSMSFn,
    commit: CommitFn,
    reject: RejectFn | None = None,
) -> list[dict[str, Any]]:
    """Handle a batch of records sequentially using `handle_message`."""
    results: list[dict[str, Any]] = []
    for record in records:
        result = handle_message(
            record,
            send_email=send_email,
            send_sms=send_sms,
            commit=commit,
            reject=reject,
        )
        results.append(result)
    return results


def _get_record_payload(record: Record) -> EventDict:
    payload = record.get("value")
    if not isinstance(payload, dict):
        raise ValueError("record.value must be a dict payload")
    return payload


def _record_meta(record: Record) -> dict[str, Any]:
    return {
        "topic": record.get("topic"),
        "partition": record.get("partition"),
        "offset": record.get("offset"),
    }
