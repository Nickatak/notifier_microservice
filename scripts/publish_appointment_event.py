#!/usr/bin/env python3
"""Publish one `appointments.created` event to Kafka for local testing."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Allow running this file directly from repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from notifications.adapters.kafka_runtime import publish_appointment_created_event  # noqa: E402


def main() -> int:
    _load_env_file(REPO_ROOT / ".env")
    args = parse_args()
    payload = build_payload(args)
    metadata = publish_appointment_created_event(payload, topic=args.topic)

    print("[PUBLISHED]")
    print(f"topic={metadata['topic']}")
    print(f"partition={metadata['partition']}")
    print(f"offset={metadata['offset']}")
    print(f"event_id={payload['event_id']}")
    print(f"notify.email={payload['notify']['email']} notify.sms={payload['notify']['sms']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish one appointments.created event for Kafka testing."
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Recipient email for the appointment event.",
    )
    parser.add_argument(
        "--phone-e164",
        default=None,
        help="Optional phone in E.164 format (required only if --notify-sms).",
    )
    parser.add_argument(
        "--notify-sms",
        action="store_true",
        help="Set notify.sms=true in the published event.",
    )
    parser.add_argument(
        "--event-id",
        default=None,
        help="Optional event id. Default: generated UUID.",
    )
    parser.add_argument(
        "--appointment-id",
        default=None,
        help="Optional appointment id. Default: generated UUID suffix.",
    )
    parser.add_argument(
        "--user-id",
        default="user-demo-1",
        help="User id value for the event payload.",
    )
    parser.add_argument(
        "--time",
        default=None,
        help="Appointment time ISO timestamp. Default: current UTC time.",
    )
    parser.add_argument(
        "--topic",
        default=None,
        help="Override Kafka topic (defaults to KAFKA_TOPIC_APPOINTMENTS_CREATED).",
    )
    return parser.parse_args()


def build_payload(args: argparse.Namespace) -> dict[str, object]:
    if args.notify_sms and not args.phone_e164:
        raise SystemExit("--phone-e164 is required when --notify-sms is enabled.")

    event_id = args.event_id or f"evt-{uuid.uuid4()}"
    appointment_id = args.appointment_id or f"apt-{uuid.uuid4().hex[:12]}"
    appointment_time = args.time or datetime.now(tz=UTC).isoformat()

    appointment: dict[str, object] = {
        "appointment_id": appointment_id,
        "user_id": args.user_id,
        "time": appointment_time,
        "email": args.email,
    }
    if args.phone_e164:
        appointment["phone_e164"] = args.phone_e164

    return {
        "event_id": event_id,
        "event_type": "appointments.created",
        "occurred_at": datetime.now(tz=UTC).isoformat(),
        "notify": {
            "email": True,
            "sms": bool(args.notify_sms),
        },
        "appointment": appointment,
    }


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        os.environ.setdefault(key, value)


if __name__ == "__main__":
    sys.exit(main())

