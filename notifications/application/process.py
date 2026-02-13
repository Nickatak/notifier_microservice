"""Application orchestration for notification channel execution.

Mental model refresher:
- Application layer coordinates use-case flow across domain modules.
- It is the right place for cross-channel or cross-topic workflow logic.
- In this project it:
  1) calls email domain logic
  2) calls sms domain logic
  3) aggregates a single success signal used for commit decisions
"""

from __future__ import annotations

from ..domain.email import send_email_notification
from ..domain.sms import send_sms_notification
from ..types import Event, ProcessingResult, SendEmailFn, SendSMSFn


def process_notification_event(
    event: Event,
    send_email: SendEmailFn,
    send_sms: SendSMSFn,
) -> ProcessingResult:
    """Execute the notification use-case for one normalized event."""
    email_result = send_email_notification(event, send_email)
    sms_result = send_sms_notification(event, send_sms)
    channel_results = [email_result, sms_result]

    all_requested_succeeded = all(
        (not item["requested"]) or item["success"] for item in channel_results
    )

    return {
        "event_id": event.get("event_id"),
        "appointment_id": event.get("appointment_id"),
        "channel_results": channel_results,
        "all_requested_succeeded": all_requested_succeeded,
    }
