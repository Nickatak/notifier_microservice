"""Real provider adapters for production-like sending.

Mental model refresher:
- This module is an outbound adapter.
- It integrates with external providers using environment-variable config.
- Domain/application code only sees simple callable sender functions.

Operational note (2026-02-13):
- Twilio account is upgraded to paid.
- Toll-free verification has been submitted for the SMS sender number.
- Until approval, Twilio may accept the API request but still return final
  delivery failures for US/Canada traffic.
"""

from __future__ import annotations

import base64
import os
import urllib.error
import urllib.parse
import urllib.request


def send_email_via_mailgun_from_env(*, to_email: str, subject: str, body: str) -> None:
    """Send email via Mailgun REST API using environment-variable config."""
    api_key = _required_env("MAILGUN_API_KEY")
    domain = _required_env("MAILGUN_DOMAIN")
    from_email = _required_env("MAILGUN_FROM_EMAIL")
    base_url = os.getenv("MAILGUN_API_BASE_URL", "https://api.mailgun.net").rstrip("/")
    timeout_seconds = float(os.getenv("MAILGUN_TIMEOUT_SECONDS", "10"))

    encoded_domain = urllib.parse.quote(domain, safe="")
    endpoint = f"{base_url}/v3/{encoded_domain}/messages"
    payload = urllib.parse.urlencode(
        {"from": from_email, "to": to_email, "subject": subject, "text": body}
    ).encode("utf-8")

    request = urllib.request.Request(endpoint, data=payload, method="POST")
    request.add_header("Authorization", _basic_auth_header("api", api_key))
    request.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(response.getcode())
            if status < 200 or status >= 300:
                raise RuntimeError(f"Mailgun email send failed with status {status}")
            response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Mailgun email send failed HTTP {exc.code}: {details[:300]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Mailgun email send failed: {exc.reason}") from exc


def send_sms_via_twilio_from_env(*, to_phone_e164: str, message: str) -> None:
    """Send SMS via Twilio REST API using environment-variable config."""
    account_sid = _required_env("TWILIO_ACCOUNT_SID")
    auth_token = _required_env("TWILIO_AUTH_TOKEN")
    from_phone = _required_env("TWILIO_FROM_PHONE")
    base_url = os.getenv("TWILIO_API_BASE_URL", "https://api.twilio.com").rstrip("/")
    timeout_seconds = float(os.getenv("TWILIO_TIMEOUT_SECONDS", "10"))

    endpoint = f"{base_url}/2010-04-01/Accounts/{account_sid}/Messages.json"
    payload = urllib.parse.urlencode(
        {"To": to_phone_e164, "From": from_phone, "Body": message}
    ).encode("utf-8")
    auth_header = _basic_auth_header(account_sid, auth_token)

    request = urllib.request.Request(endpoint, data=payload, method="POST")
    request.add_header("Authorization", auth_header)
    request.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(response.getcode())
            if status < 200 or status >= 300:
                raise RuntimeError(f"Twilio SMS send failed with status {status}")
            response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Twilio SMS send failed HTTP {exc.code}: {details[:300]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Twilio SMS send failed: {exc.reason}") from exc


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


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


def _basic_auth_header(username: str, password: str) -> str:
    token = f"{username}:{password}".encode("utf-8")
    encoded = base64.b64encode(token).decode("ascii")
    return f"Basic {encoded}"
