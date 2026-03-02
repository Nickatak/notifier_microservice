"""Email channel decision logic.

Mental model refresher:
- Domain modules hold channel/business rules.
- They decide what should happen for this channel:
  - is this channel requested?
  - is required data present?
  - what message content should be sent?
- They do not parse Kafka records or commit offsets.

Recipient model:
- Emails go to the portfolio owner (NOTIFICATIONS_OWNER_EMAIL), not the
  appointment booker.  See docs/RECIPIENT_MODEL.md for details.
"""

from __future__ import annotations

from datetime import datetime

from ..types import ChannelResult, Event, SendEmailFn


def send_email_notification(event: Event, send_email: SendEmailFn) -> ChannelResult:
    """Run email-channel rules and return a plain channel result dictionary."""
    if not event.get("notify_email", False):
        return {"channel": "email", "requested": False, "success": True, "error": None}

    contact_email = event.get("email")
    notification_email = event.get("notification_email") or contact_email
    if not notification_email:
        return {
            "channel": "email",
            "requested": True,
            "success": False,
            "error": "notify.email=true but appointment.email is missing",
        }

    date_str, time_str, short_date = _format_appointment_time(
        event.get("appointment_time", "")
    )

    subject = f"New Appointment \u2014 {short_date}" if short_date else "New Appointment"

    body = _build_plain_body(date_str, time_str, contact_email, event.get("phone_e164"))
    html = _build_html_body(date_str, time_str, contact_email, event.get("phone_e164"))

    try:
        send_email(
            to_email=notification_email, subject=subject, body=body, html=html
        )
    except Exception as exc:  # pragma: no cover - error path asserted via tests
        return {"channel": "email", "requested": True, "success": False, "error": str(exc)}

    return {"channel": "email", "requested": True, "success": True, "error": None}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_appointment_time(raw: str) -> tuple[str, str, str]:
    """Parse an ISO timestamp into (date_display, time_display, short_date).

    Returns empty strings for any component that can't be parsed.
    """
    if not raw:
        return ("", "", "")
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return (raw, "", "")

    date_display = dt.strftime("%A, %B %-d, %Y")       # Thursday, February 20, 2026
    time_display = dt.strftime("%-I:%M %p") + " (PST)"  # 3:00 PM (PST)
    short_date = dt.strftime("%a, %b %-d at %-I:%M %p") # Thu, Feb 20 at 3:00 PM
    return (date_display, time_display, short_date)


def _build_plain_body(
    date_str: str, time_str: str, contact_email: str | None, phone: str | None
) -> str:
    lines = ["New appointment booked.", ""]
    if date_str:
        lines.append(f"Date:    {date_str}")
    if time_str:
        lines.append(f"Time:    {time_str}")
    if contact_email:
        lines.append(f"Contact: {contact_email}")
    if phone:
        lines.append(f"Phone:   {phone}")
    lines += ["", "\u2014", "Automated notification from your portfolio."]
    return "\n".join(lines)


def _build_html_body(
    date_str: str, time_str: str, contact_email: str | None, phone: str | None
) -> str:
    rows = ""
    td_label = (
        'style="padding: 4px 16px 4px 0; font-weight: 600; '
        'color: #666; white-space: nowrap;"'
    )
    td_value = 'style="padding: 4px 0;"'
    if date_str:
        rows += f"<tr><td {td_label}>Date</td><td {td_value}>{_esc(date_str)}</td></tr>"
    if time_str:
        rows += f"<tr><td {td_label}>Time</td><td {td_value}>{_esc(time_str)}</td></tr>"
    if contact_email:
        rows += (
            f"<tr><td {td_label}>Contact</td>"
            f"<td {td_value}>{_esc(contact_email)}</td></tr>"
        )
    if phone:
        rows += f"<tr><td {td_label}>Phone</td><td {td_value}>{_esc(phone)}</td></tr>"

    return (
        '<div style="font-family: sans-serif; max-width: 520px; '
        'margin: 0 auto; color: #333;">'
        '<h2 style="color: #14b8a6; margin: 0 0 16px 0;">New Appointment</h2>'
        f'<table style="border-collapse: collapse;">{rows}</table>'
        '<hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">'
        '<p style="font-size: 12px; color: #999; margin: 0;">'
        "Automated notification from your portfolio.</p>"
        "</div>"
    )


def _esc(text: str) -> str:
    """Minimal HTML escaping for dynamic values."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
