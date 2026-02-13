"""Payload adapter functions.

Mental model refresher:
- This is an adapter/edge module.
- It translates transport-shaped data (Kafka message payload) into the internal
  event dictionary used by application/domain code.
- It should validate shape/basic required fields, but it should not decide
  business outcomes like commit/no-commit.
"""

from __future__ import annotations

from typing import Any

from ..types import Event, EventDict


def parse_event_payload(payload: Event) -> EventDict:
    """Normalize Kafka-style payload into a plain event dictionary.

    This is the first handoff from transport data to internal data.
    """
    appointment = payload.get("appointment", {}) or {}
    notify = payload.get("notify", {}) or {}

    return {
        "event_id": _as_required_str(payload.get("event_id"), "event_id"),
        "appointment_id": _as_required_str(
            appointment.get("appointment_id"), "appointment.appointment_id"
        ),
        "user_id": str(appointment.get("user_id", "")),
        "appointment_time": str(appointment.get("time", "")),
        "email": _as_optional_str(appointment.get("email")),
        "phone_e164": _as_optional_str(appointment.get("phone_e164")),
        "notify_email": bool(notify.get("email", False)),
        "notify_sms": bool(notify.get("sms", False)),
    }


def _as_required_str(value: Any, field_name: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise ValueError(f"Missing required field: {field_name}")
    return text


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
