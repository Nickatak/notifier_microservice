"""Notification channel primitives for pre-Kafka local development."""

from .channels import (
    handle_batch,
    handle_message,
    parse_event_payload,
    publish_appointment_created_event,
    process_notification_event,
    run_email_worker_forever,
    send_email_via_console,
    send_email_via_mailgun_from_env,
    send_email_notification,
    send_sms_via_console,
    send_sms_via_twilio_from_env,
    send_sms_notification,
)

__all__ = [
    "handle_batch",
    "handle_message",
    "parse_event_payload",
    "publish_appointment_created_event",
    "process_notification_event",
    "run_email_worker_forever",
    "send_email_via_console",
    "send_email_via_mailgun_from_env",
    "send_email_notification",
    "send_sms_via_console",
    "send_sms_via_twilio_from_env",
    "send_sms_notification",
]
