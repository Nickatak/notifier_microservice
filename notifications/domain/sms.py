"""SMS channel decision logic.

Mental model refresher:
- Domain modules hold channel/business rules.
- They decide what should happen for this channel:
  - is this channel requested?
  - is required data present?
  - what message content should be sent?
- They do not parse Kafka records or commit offsets.
"""

from __future__ import annotations

from ..types import ChannelResult, Event, SendSMSFn


def send_sms_notification(event: Event, send_sms: SendSMSFn) -> ChannelResult:
    """Run SMS-channel rules and return a plain channel result dictionary."""
    if not event.get("notify_sms", False):
        return {"channel": "sms", "requested": False, "success": True, "error": None}

    phone = event.get("phone_e164")
    if not phone:
        return {
            "channel": "sms",
            "requested": True,
            "success": False,
            "error": "notify.sms=true but appointment.phone_e164 is missing",
        }

    message = (
        f"Appointment {event.get('appointment_id', '')} confirmed for "
        f"{event.get('appointment_time', '')}."
    )

    try:
        send_sms(to_phone_e164=phone, message=message)
    except Exception as exc:  # pragma: no cover - error path asserted via tests
        return {"channel": "sms", "requested": True, "success": False, "error": str(exc)}

    return {"channel": "sms", "requested": True, "success": True, "error": None}
