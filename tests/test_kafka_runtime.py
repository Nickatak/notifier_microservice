from __future__ import annotations

import unittest
from unittest import mock

from notifications.adapters import kafka_runtime


class KafkaRuntimeHelperTests(unittest.TestCase):
    def test_deserialize_json_object_accepts_bytes(self) -> None:
        payload = kafka_runtime._deserialize_json_object(
            b'{"event_id":"evt-1","notify":{"email":true,"sms":false}}'
        )
        self.assertEqual(payload["event_id"], "evt-1")
        self.assertEqual(payload["notify"]["sms"], False)

    def test_deserialize_json_object_rejects_non_object_json(self) -> None:
        with self.assertRaises(ValueError):
            kafka_runtime._deserialize_json_object(b'["not","an","object"]')

    def test_with_sms_disabled_forces_notify_sms_false(self) -> None:
        payload = {
            "event_id": "evt-1",
            "notify": {"email": True, "sms": True},
            "appointment": {"appointment_id": "apt-1"},
        }
        transformed = kafka_runtime._with_sms_disabled(payload)

        self.assertEqual(transformed["notify"]["sms"], False)
        self.assertEqual(payload["notify"]["sms"], True)

    def test_bootstrap_servers_from_env_parses_csv(self) -> None:
        env = {"KAFKA_BOOTSTRAP_SERVERS": "localhost:9092, kafka:29092 "}
        with mock.patch.dict("os.environ", env, clear=True):
            servers = kafka_runtime._bootstrap_servers_from_env()
        self.assertEqual(servers, ["localhost:9092", "kafka:29092"])

    def test_bootstrap_servers_from_env_requires_value(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                kafka_runtime._bootstrap_servers_from_env()

    def test_offset_and_metadata_prefers_three_arg_signature(self) -> None:
        calls: list[tuple[int, str, object | None]] = []

        def factory(offset: int, metadata: str, leader_epoch: object | None) -> tuple[int, str]:
            calls.append((offset, metadata, leader_epoch))
            return (offset, metadata)

        built = kafka_runtime._offset_and_metadata(factory, 99)
        self.assertEqual(built, (99, ""))
        self.assertEqual(calls, [(99, "", -1)])

    def test_offset_and_metadata_falls_back_to_two_arg_signature(self) -> None:
        calls: list[tuple[int, str]] = []

        def factory(offset: int, metadata: str) -> tuple[int, str]:
            calls.append((offset, metadata))
            return (offset, metadata)

        built = kafka_runtime._offset_and_metadata(factory, 42)
        self.assertEqual(built, (42, ""))
        self.assertEqual(calls, [(42, "")])

    def test_to_json_compatible_converts_non_json_types(self) -> None:
        value = {
            "raw_bytes": b"abc",
            "nested": {"items": [1, b"\xff", {"ok": True}]},
            "set_value": {"a", "b"},
            "object": object(),
        }

        converted = kafka_runtime._to_json_compatible(value)

        self.assertEqual(converted["raw_bytes"], "abc")
        self.assertEqual(converted["nested"]["items"][0], 1)
        self.assertEqual(converted["nested"]["items"][1], "\ufffd")
        self.assertIsInstance(converted["set_value"], list)
        self.assertIsInstance(converted["object"], str)

    def test_build_dlq_payload_includes_source_metadata_and_event_id(self) -> None:
        source_payload = {
            "event_id": "evt-abc",
            "notify": {"email": True, "sms": False},
        }

        dlq_payload = kafka_runtime._build_dlq_payload(
            source_topic="appointments.created",
            source_partition=0,
            source_offset=42,
            source_payload=source_payload,
            failure_reason="one_or_more_requested_channels_failed",
        )

        self.assertEqual(dlq_payload["event_type"], "appointments.created.dlq")
        self.assertEqual(dlq_payload["failure_reason"], "one_or_more_requested_channels_failed")
        self.assertEqual(dlq_payload["source"]["topic"], "appointments.created")
        self.assertEqual(dlq_payload["source"]["partition"], 0)
        self.assertEqual(dlq_payload["source"]["offset"], 42)
        self.assertEqual(dlq_payload["source_event_id"], "evt-abc")
        self.assertIn("failed_at", dlq_payload)


if __name__ == "__main__":
    unittest.main()
