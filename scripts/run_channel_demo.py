#!/usr/bin/env python3
"""Run notification channels locally without Kafka.

Operational note (2026-02-13):
- Use this script for local channel-flow testing while SMS live-send validation
  is paused pending Twilio toll-free verification approval.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow running this file directly from repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from notifications.channels import (
    parse_event_payload,
    process_notification_event,
    send_email_via_console,
    send_sms_via_console,
)


def main() -> int:
    args = parse_args()
    payload = load_payload(args.payload_file)
    event = parse_event_payload(payload)
    result = process_notification_event(
        event=event,
        send_email=send_email_via_console,
        send_sms=send_sms_via_console,
    )

    print("")
    print("[SUMMARY]")
    print(f"event_id={result['event_id']}")
    print(f"appointment_id={result['appointment_id']}")
    for item in result["channel_results"]:
        print(
            f"channel={item['channel']} requested={item['requested']} "
            f"success={item['success']} error={item['error']}"
        )
    print(f"all_requested_succeeded={result['all_requested_succeeded']}")
    return 0 if result["all_requested_succeeded"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute email/sms channel logic with a sample payload."
    )
    parser.add_argument(
        "--payload-file",
        type=Path,
        default=None,
        help="Optional JSON file matching appointments.created event shape.",
    )
    return parser.parse_args()


def load_payload(payload_file: Path | None) -> dict[str, Any]:
    if payload_file is None:
        return sample_payload()
    with payload_file.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def sample_payload() -> dict[str, Any]:
    return {
        "event_id": "evt-demo-1",
        "event_type": "appointments.created",
        "occurred_at": "2026-02-13T19:35:00Z",
        "notify": {"email": True, "sms": True},
        "appointment": {
            "appointment_id": "apt-demo-1",
            "user_id": "user-demo-1",
            "time": "2026-02-20T15:00:00Z",
            "email": "user@example.com",
            "phone_e164": "+15555550123",
        },
    }


if __name__ == "__main__":
    sys.exit(main())
