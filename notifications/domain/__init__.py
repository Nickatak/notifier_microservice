"""Domain layer: channel-specific decision logic."""

from .email import send_email_notification
from .sms import send_sms_notification

__all__ = [
    "send_email_notification",
    "send_sms_notification",
]

