from __future__ import annotations

import unittest

from notifications.channels import (
    parse_event_payload,
    process_notification_event,
    send_email_notification,
    send_sms_notification,
)


def make_event(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "event_id": "evt-1",
        "appointment_id": "apt-1",
        "user_id": "user-1",
        "appointment_time": "2026-02-20T15:00:00Z",
        "email": "person@example.com",
        "phone_e164": "+15555550123",
        "notify_email": True,
        "notify_sms": True,
    }
    return base | overrides


class ChannelFunctionTests(unittest.TestCase):
    def test_send_email_notification_success(self) -> None:
        event = make_event(notify_sms=False)
        sent: list[dict[str, str]] = []

        def fake_send_email(*, to_email: str, subject: str, body: str) -> None:
            sent.append({"to_email": to_email, "subject": subject, "body": body})

        result = send_email_notification(event, fake_send_email)

        self.assertTrue(result["requested"])
        self.assertTrue(result["success"])
        self.assertEqual(len(sent), 1)

    def test_send_email_notification_missing_email(self) -> None:
        event = make_event(email=None, notify_sms=False)
        sent: list[dict[str, str]] = []

        def fake_send_email(*, to_email: str, subject: str, body: str) -> None:
            sent.append({"to_email": to_email, "subject": subject, "body": body})

        result = send_email_notification(event, fake_send_email)

        self.assertTrue(result["requested"])
        self.assertFalse(result["success"])
        self.assertIn("appointment.email", result["error"] or "")
        self.assertEqual(sent, [])

    def test_send_sms_notification_success(self) -> None:
        event = make_event(notify_email=False)
        sent: list[dict[str, str]] = []

        def fake_send_sms(*, to_phone_e164: str, message: str) -> None:
            sent.append({"to_phone_e164": to_phone_e164, "message": message})

        result = send_sms_notification(event, fake_send_sms)

        self.assertTrue(result["requested"])
        self.assertTrue(result["success"])
        self.assertEqual(len(sent), 1)

    def test_send_sms_notification_missing_phone(self) -> None:
        event = make_event(phone_e164=None, notify_email=False)
        sent: list[dict[str, str]] = []

        def fake_send_sms(*, to_phone_e164: str, message: str) -> None:
            sent.append({"to_phone_e164": to_phone_e164, "message": message})

        result = send_sms_notification(event, fake_send_sms)

        self.assertTrue(result["requested"])
        self.assertFalse(result["success"])
        self.assertIn("appointment.phone_e164", result["error"] or "")
        self.assertEqual(sent, [])


class ProcessingTests(unittest.TestCase):
    def test_process_notification_event_both_requested_success(self) -> None:
        event = make_event()
        sent_emails: list[dict[str, str]] = []
        sent_sms: list[dict[str, str]] = []

        def fake_send_email(*, to_email: str, subject: str, body: str) -> None:
            sent_emails.append({"to_email": to_email, "subject": subject, "body": body})

        def fake_send_sms(*, to_phone_e164: str, message: str) -> None:
            sent_sms.append({"to_phone_e164": to_phone_e164, "message": message})

        result = process_notification_event(event, fake_send_email, fake_send_sms)

        self.assertTrue(result["all_requested_succeeded"])
        self.assertEqual(len(sent_emails), 1)
        self.assertEqual(len(sent_sms), 1)

    def test_process_notification_event_one_channel_fails(self) -> None:
        event = make_event()
        sent_emails: list[dict[str, str]] = []

        def fake_send_email(*, to_email: str, subject: str, body: str) -> None:
            sent_emails.append({"to_email": to_email, "subject": subject, "body": body})

        def fake_send_sms(*, to_phone_e164: str, message: str) -> None:
            raise RuntimeError("sms provider unavailable")

        result = process_notification_event(event, fake_send_email, fake_send_sms)

        self.assertFalse(result["all_requested_succeeded"])
        sms_result = next(
            item for item in result["channel_results"] if item["channel"] == "sms"
        )
        self.assertFalse(sms_result["success"])
        self.assertIn("sms provider unavailable", sms_result["error"] or "")


class EventModelTests(unittest.TestCase):
    def test_parse_event_payload_maps_kafka_style_payload(self) -> None:
        payload = {
            "event_id": "evt-2",
            "notify": {"email": True, "sms": False},
            "appointment": {
                "appointment_id": "apt-2",
                "user_id": "user-2",
                "time": "2026-02-22T18:30:00Z",
                "email": "new@example.com",
            },
        }

        event = parse_event_payload(payload)

        self.assertEqual(event["event_id"], "evt-2")
        self.assertEqual(event["appointment_id"], "apt-2")
        self.assertTrue(event["notify_email"])
        self.assertFalse(event["notify_sms"])

    def test_parse_event_payload_requires_event_id(self) -> None:
        payload = {
            "notify": {"email": True, "sms": False},
            "appointment": {"appointment_id": "apt-2"},
        }

        with self.assertRaises(ValueError):
            parse_event_payload(payload)


if __name__ == "__main__":
    unittest.main()
