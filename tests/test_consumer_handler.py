from __future__ import annotations

import unittest
from typing import Any

from notifications.adapters.consumer_handler import handle_batch, handle_message


def make_record(value: dict[str, Any], *, offset: int) -> dict[str, Any]:
    return {
        "topic": "appointments.created",
        "partition": 0,
        "offset": offset,
        "value": value,
    }


def make_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "event_id": "evt-1",
        "notify": {"email": True, "sms": True},
        "appointment": {
            "appointment_id": "apt-1",
            "user_id": "user-1",
            "time": "2026-02-20T15:00:00Z",
            "email": "person@example.com",
            "phone_e164": "+15555550123",
        },
    }
    return base | overrides


class ConsumerHandlerTests(unittest.TestCase):
    def test_handle_message_commits_when_all_requested_channels_succeed(self) -> None:
        record = make_record(make_payload(), offset=10)
        committed: list[int] = []
        rejected: list[int] = []

        def send_email(*, to_email: str, subject: str, body: str) -> None:
            return None

        def send_sms(*, to_phone_e164: str, message: str) -> None:
            return None

        def commit(message_record: dict[str, Any]) -> None:
            committed.append(int(message_record["offset"]))

        def reject(message_record: dict[str, Any], reason: str) -> None:
            rejected.append(int(message_record["offset"]))

        result = handle_message(
            record,
            send_email=send_email,
            send_sms=send_sms,
            commit=commit,
            reject=reject,
        )

        self.assertEqual(result["status"], "processed_and_committed")
        self.assertTrue(result["should_commit"])
        self.assertEqual(committed, [10])
        self.assertEqual(rejected, [])

    def test_handle_message_does_not_commit_when_channel_fails(self) -> None:
        payload = make_payload()
        record = make_record(payload, offset=11)
        committed: list[int] = []
        rejected: list[int] = []

        def send_email(*, to_email: str, subject: str, body: str) -> None:
            return None

        def send_sms(*, to_phone_e164: str, message: str) -> None:
            raise RuntimeError("sms provider unavailable")

        def commit(message_record: dict[str, Any]) -> None:
            committed.append(int(message_record["offset"]))

        def reject(message_record: dict[str, Any], reason: str) -> None:
            rejected.append(int(message_record["offset"]))

        result = handle_message(
            record,
            send_email=send_email,
            send_sms=send_sms,
            commit=commit,
            reject=reject,
        )

        self.assertEqual(result["status"], "processed_not_committed")
        self.assertFalse(result["should_commit"])
        self.assertEqual(committed, [])
        self.assertEqual(rejected, [11])

    def test_handle_message_parse_failure_does_not_commit(self) -> None:
        bad_record = {
            "topic": "appointments.created",
            "partition": 0,
            "offset": 12,
            "value": {"notify": {"email": True, "sms": False}, "appointment": {}},
        }
        committed: list[int] = []
        rejected: list[int] = []

        def send_email(*, to_email: str, subject: str, body: str) -> None:
            return None

        def send_sms(*, to_phone_e164: str, message: str) -> None:
            return None

        def commit(message_record: dict[str, Any]) -> None:
            committed.append(int(message_record["offset"]))

        def reject(message_record: dict[str, Any], reason: str) -> None:
            rejected.append(int(message_record["offset"]))

        result = handle_message(
            bad_record,
            send_email=send_email,
            send_sms=send_sms,
            commit=commit,
            reject=reject,
        )

        self.assertEqual(result["status"], "parse_failed")
        self.assertFalse(result["should_commit"])
        self.assertEqual(committed, [])
        self.assertEqual(rejected, [12])
        self.assertIn("parse_failed", result["error"] or "")

    def test_handle_batch_mixes_commit_and_no_commit(self) -> None:
        records = [
            make_record(make_payload(), offset=20),
            make_record(
                make_payload(
                    notify={"email": False, "sms": True},
                    appointment={
                        "appointment_id": "apt-2",
                        "user_id": "user-2",
                        "time": "2026-02-20T16:00:00Z",
                        "email": "person@example.com",
                    },
                ),
                offset=21,
            ),
        ]
        committed: list[int] = []
        rejected: list[int] = []

        def send_email(*, to_email: str, subject: str, body: str) -> None:
            return None

        def send_sms(*, to_phone_e164: str, message: str) -> None:
            return None

        def commit(message_record: dict[str, Any]) -> None:
            committed.append(int(message_record["offset"]))

        def reject(message_record: dict[str, Any], reason: str) -> None:
            rejected.append(int(message_record["offset"]))

        results = handle_batch(
            records,
            send_email=send_email,
            send_sms=send_sms,
            commit=commit,
            reject=reject,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(committed, [20])
        self.assertEqual(rejected, [21])


if __name__ == "__main__":
    unittest.main()

