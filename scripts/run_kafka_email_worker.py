#!/usr/bin/env python3
"""Run the Kafka email worker.

This worker consumes `appointments.created` and sends email via Mailgun.
By default, SMS is forced off (`notify.sms=false`) while Twilio toll-free
verification is pending.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow running this file directly from repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from notifications.adapters.kafka_runtime import run_email_worker_forever  # noqa: E402


def main() -> int:
    parse_args()
    _load_env_file(REPO_ROOT / ".env")
    return run_email_worker_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Kafka consumer loop for email notifications."
    )
    return parser.parse_args()


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
