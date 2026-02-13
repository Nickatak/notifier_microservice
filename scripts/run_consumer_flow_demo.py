#!/usr/bin/env python3
"""Run a Kafka-like consumer flow without Kafka."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Allow running this file directly from repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from notifications.adapters.fake_senders import (  # noqa: E402
    send_email_via_console,
    send_sms_via_console,
)
from notifications.adapters.consumer_handler import handle_batch  # noqa: E402


def main() -> int:
    records = sample_records()
    committed_offsets: list[tuple[int, int]] = []
    rejected_offsets: list[tuple[int, int, str]] = []

    def commit(record: dict[str, Any]) -> None:
        partition = int(record.get("partition", -1))
        offset = int(record.get("offset", -1))
        committed_offsets.append((partition, offset))
        print(f"[COMMIT] partition={partition} offset={offset}")

    def reject(record: dict[str, Any], reason: str) -> None:
        partition = int(record.get("partition", -1))
        offset = int(record.get("offset", -1))
        rejected_offsets.append((partition, offset, reason))
        print(f"[NO-COMMIT] partition={partition} offset={offset} reason={reason}")

    results = handle_batch(
        records,
        send_email=send_email_maybe_fail,
        send_sms=send_sms_maybe_fail,
        commit=commit,
        reject=reject,
    )

    print("")
    print("[BATCH SUMMARY]")
    for result in results:
        meta = result["record_meta"]
        print(
            f"offset={meta['offset']} status={result['status']} "
            f"should_commit={result['should_commit']} error={result['error']}"
        )

    print("")
    print("[OFFSETS]")
    print(f"committed={committed_offsets}")
    print(f"rejected={rejected_offsets}")
    return 0


def send_email_maybe_fail(*, to_email: str, subject: str, body: str) -> None:
    if to_email == "fail-email@example.com":
        raise RuntimeError("email provider unavailable")
    send_email_via_console(to_email=to_email, subject=subject, body=body)


def send_sms_maybe_fail(*, to_phone_e164: str, message: str) -> None:
    if to_phone_e164 == "+15555559999":
        raise RuntimeError("sms provider unavailable")
    send_sms_via_console(to_phone_e164=to_phone_e164, message=message)


def sample_records() -> list[dict[str, Any]]:
    return [
        {
            "topic": "appointments.created",
            "partition": 0,
            "offset": 100,
            "value": {
                "event_id": "evt-100",
                "notify": {"email": True, "sms": True},
                "appointment": {
                    "appointment_id": "apt-100",
                    "user_id": "user-100",
                    "time": "2026-02-20T15:00:00Z",
                    "email": "person@example.com",
                    "phone_e164": "+15555550123",
                },
            },
        },
        {
            "topic": "appointments.created",
            "partition": 0,
            "offset": 101,
            "value": {
                "event_id": "evt-101",
                "notify": {"email": False, "sms": True},
                "appointment": {
                    "appointment_id": "apt-101",
                    "user_id": "user-101",
                    "time": "2026-02-20T16:00:00Z",
                    "email": "person@example.com",
                },
            },
        },
        {
            "topic": "appointments.created",
            "partition": 0,
            "offset": 102,
            "value": {
                "notify": {"email": True, "sms": False},
                "appointment": {
                    "appointment_id": "apt-102",
                    "user_id": "user-102",
                    "time": "2026-02-20T17:00:00Z",
                    "email": "person@example.com",
                },
            },
        },
        {
            "topic": "appointments.created",
            "partition": 0,
            "offset": 103,
            "value": {
                "event_id": "evt-103",
                "notify": {"email": True, "sms": False},
                "appointment": {
                    "appointment_id": "apt-103",
                    "user_id": "user-103",
                    "time": "2026-02-20T18:00:00Z",
                    "email": "fail-email@example.com",
                },
            },
        },
    ]


if __name__ == "__main__":
    sys.exit(main())

