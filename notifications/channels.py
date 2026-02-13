"""Compatibility facade for notification functions.

Module layout by abstraction layer:
- adapters: payload mapping and sender adapters
- domain: email/sms decision logic
- application: orchestration across channels
"""

from .adapters.fake_senders import send_email_via_console, send_sms_via_console
from .adapters.consumer_handler import handle_batch, handle_message
from .adapters.kafka_runtime import publish_appointment_created_event, run_email_worker_forever
from .adapters.payload import parse_event_payload
from .adapters.real_senders import (
    send_email_via_mailgun_from_env,
    send_sms_via_twilio_from_env,
)
from .application.process import process_notification_event
from .domain.email import send_email_notification
from .domain.sms import send_sms_notification

__all__ = [
    "handle_batch",
    "handle_message",
    "parse_event_payload",
    "publish_appointment_created_event",
    "send_email_notification",
    "send_sms_notification",
    "process_notification_event",
    "run_email_worker_forever",
    "send_email_via_console",
    "send_email_via_mailgun_from_env",
    "send_sms_via_console",
    "send_sms_via_twilio_from_env",
]
