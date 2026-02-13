"""Email channel decision logic.

Mental model refresher:
- Domain modules hold channel/business rules.
- They decide what should happen for this channel:
  - is this channel requested?
  - is required data present?
  - what message content should be sent?
- They do not parse Kafka records or commit offsets.
"""

from __future__ import annotations

from ..types import ChannelResult, Event, SendEmailFn


def send_email_notification(event: Event, send_email: SendEmailFn) -> ChannelResult:
    """Run email-channel rules and return a plain channel result dictionary."""
    if not event.get("notify_email", False):
        return {"channel": "email", "requested": False, "success": True, "error": None}

    email = event.get("email")
    if not email:
        return {
            "channel": "email",
            "requested": True,
            "success": False,
            "error": "notify.email=true but appointment.email is missing",
        }

    subject = f"Appointment confirmed: {event.get('appointment_time', '')}"
    body = (
        f"Appointment {event.get('appointment_id', '')} is confirmed for "
        f"{event.get('appointment_time', '')}."
    )

    try:
        send_email(to_email=email, subject=subject, body=body)
    except Exception as exc:  # pragma: no cover - error path asserted via tests
        return {"channel": "email", "requested": True, "success": False, "error": str(exc)}

    return {"channel": "email", "requested": True, "success": True, "error": None}
