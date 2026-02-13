"""Fake sender adapters for local smoke tests.

Mental model refresher:
- This is outbound adapter code.
- In production, this is where provider SDK/API calls live (SMTP, Twilio, etc).
- Domain code calls these through injected functions; domain does not know which
  provider implementation is underneath.
"""

from __future__ import annotations


def send_email_via_console(*, to_email: str, subject: str, body: str) -> None:
    print("[EMAIL]")
    print(f"to={to_email}")
    print(f"subject={subject}")
    print(f"body={body}")


def send_sms_via_console(*, to_phone_e164: str, message: str) -> None:
    print("[SMS]")
    print(f"to={to_phone_e164}")
    print(f"message={message}")
