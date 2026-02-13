"""Adapter layer: external payload mapping and sender implementations."""

from .fake_senders import send_email_via_console, send_sms_via_console
from .consumer_handler import handle_batch, handle_message
from .kafka_runtime import publish_appointment_created_event, run_email_worker_forever
from .payload import parse_event_payload
from .real_senders import send_email_via_mailgun_from_env, send_sms_via_twilio_from_env

__all__ = [
    "handle_batch",
    "handle_message",
    "parse_event_payload",
    "publish_appointment_created_event",
    "run_email_worker_forever",
    "send_email_via_console",
    "send_email_via_mailgun_from_env",
    "send_sms_via_console",
    "send_sms_via_twilio_from_env",
]
