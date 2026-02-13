from __future__ import annotations

import io
import os
import unittest
import urllib.error
import urllib.parse
from unittest import mock

from notifications.adapters.real_senders import (
    send_email_via_mailgun_from_env,
    send_sms_via_twilio_from_env,
)


class MailgunAdapterTests(unittest.TestCase):
    @mock.patch.dict(
        os.environ,
        {
            "MAILGUN_API_KEY": "key-123",
            "MAILGUN_DOMAIN": "sandbox.example.com",
            "MAILGUN_FROM_EMAIL": "No Reply <no-reply@sandbox.example.com>",
            "MAILGUN_TIMEOUT_SECONDS": "5",
        },
        clear=True,
    )
    @mock.patch("notifications.adapters.real_senders.urllib.request.urlopen")
    def test_send_email_via_mailgun_from_env_posts_message(
        self, urlopen_mock: mock.Mock
    ) -> None:
        response = urlopen_mock.return_value.__enter__.return_value
        response.getcode.return_value = 200
        response.read.return_value = b'{"id":"<msg-id>","message":"Queued"}'

        send_email_via_mailgun_from_env(
            to_email="user@example.com",
            subject="Hello",
            body="World",
        )

        self.assertTrue(urlopen_mock.called)
        request_obj = urlopen_mock.call_args.args[0]
        self.assertIn("/v3/sandbox.example.com/messages", request_obj.full_url)
        self.assertTrue((request_obj.get_header("Authorization") or "").startswith("Basic "))

        payload = urllib.parse.parse_qs((request_obj.data or b"").decode("utf-8"))
        self.assertEqual(payload["to"][0], "user@example.com")
        self.assertEqual(payload["subject"][0], "Hello")
        self.assertEqual(payload["text"][0], "World")
        self.assertIn("no-reply@sandbox.example.com", payload["from"][0])

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_send_email_via_mailgun_from_env_requires_config(self) -> None:
        with self.assertRaises(RuntimeError):
            send_email_via_mailgun_from_env(
                to_email="user@example.com",
                subject="x",
                body="y",
            )

    @mock.patch.dict(
        os.environ,
        {
            "MAILGUN_API_KEY": "key-123",
            "MAILGUN_DOMAIN": "sandbox.example.com",
            "MAILGUN_FROM_EMAIL": "no-reply@sandbox.example.com",
        },
        clear=True,
    )
    @mock.patch("notifications.adapters.real_senders.urllib.request.urlopen")
    def test_send_email_via_mailgun_from_env_surfaces_http_error(
        self, urlopen_mock: mock.Mock
    ) -> None:
        http_error = urllib.error.HTTPError(
            url="https://api.mailgun.net/v3/sandbox.example.com/messages",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"Forbidden"}'),
        )
        urlopen_mock.side_effect = http_error

        with self.assertRaises(RuntimeError) as exc:
            send_email_via_mailgun_from_env(
                to_email="user@example.com",
                subject="x",
                body="y",
            )

        self.assertIn("HTTP 401", str(exc.exception))


class TwilioAdapterTests(unittest.TestCase):
    @mock.patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "token-xyz",
            "TWILIO_FROM_PHONE": "+15555550111",
            "TWILIO_TIMEOUT_SECONDS": "7",
        },
        clear=True,
    )
    @mock.patch("notifications.adapters.real_senders.urllib.request.urlopen")
    def test_send_sms_via_twilio_from_env_posts_message(
        self, urlopen_mock: mock.Mock
    ) -> None:
        response = urlopen_mock.return_value.__enter__.return_value
        response.getcode.return_value = 201
        response.read.return_value = b'{"sid":"SM123"}'

        send_sms_via_twilio_from_env(
            to_phone_e164="+15555550123",
            message="hello",
        )

        self.assertTrue(urlopen_mock.called)
        request_obj = urlopen_mock.call_args.args[0]
        self.assertIn("/Accounts/AC123/Messages.json", request_obj.full_url)

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_send_sms_via_twilio_from_env_requires_credentials(self) -> None:
        with self.assertRaises(RuntimeError):
            send_sms_via_twilio_from_env(
                to_phone_e164="+15555550123",
                message="hello",
            )

    @mock.patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "token-xyz",
            "TWILIO_FROM_PHONE": "+15555550111",
        },
        clear=True,
    )
    @mock.patch("notifications.adapters.real_senders.urllib.request.urlopen")
    def test_send_sms_via_twilio_from_env_surfaces_http_error(
        self, urlopen_mock: mock.Mock
    ) -> None:
        http_error = urllib.error.HTTPError(
            url="https://api.twilio.com/x",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"invalid to phone"}'),
        )
        urlopen_mock.side_effect = http_error

        with self.assertRaises(RuntimeError) as exc:
            send_sms_via_twilio_from_env(
                to_phone_e164="+15555550123",
                message="hello",
            )

        self.assertIn("HTTP 400", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
