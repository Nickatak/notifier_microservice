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


if __name__ == "__main__":
    unittest.main()

