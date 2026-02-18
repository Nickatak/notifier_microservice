# Notifier Service (Kafka + Notifications)

Kafka broker + notification worker for the portfolio stack. This repo also
contains the reusable Python `notifications` package used by the worker.

Full stack instructions live in the parent stack repo: `../README.md`.

## Role In The System

- Hosts a local Kafka broker (Docker).
- Consumes `appointments.created` events and sends email notifications.
- Current behavior: email is owner-only; SMS is disabled.

## Dependencies

- Calendar API (producer): `../portfolio-calendar`
- BFF (consumer/read model): `../portfolio-bff`
- Frontend (source of bookings): `../portfolio-frontend`

## Local Development

Create env file:
```bash
cp .env.example .env
```

Update Mailgun + owner email in `.env`:
- `MAILGUN_API_KEY`
- `MAILGUN_DOMAIN`
- `MAILGUN_FROM_EMAIL`
- `NOTIFICATIONS_OWNER_EMAIL`

Start Kafka (Docker):
```bash
docker compose up -d kafka kafka-init
```

Run the worker locally:
```bash
python3 scripts/run_kafka_email_worker.py
```

Publish a test event:
```bash
python3 scripts/publish_appointment_event.py --email you@example.com
```

## Docker Development

```bash
docker compose up -d kafka kafka-init worker
```

Logs:
```bash
docker logs -f notifications-email-worker
```

## Environment Variables

Mailgun (required for real email):
- `MAILGUN_API_KEY`
- `MAILGUN_DOMAIN`
- `MAILGUN_FROM_EMAIL`

Owner notifications:
- `NOTIFICATIONS_OWNER_EMAIL` (recipient inbox)

Kafka:
- `KAFKA_BOOTSTRAP_SERVERS` (Docker default: `kafka:19092`)
- `KAFKA_TOPIC_APPOINTMENTS_CREATED` (default: `appointments.created`)
- `KAFKA_TOPIC_APPOINTMENTS_CREATED_DLQ` (default: `appointments.created.dlq`)
- `KAFKA_GROUP_ID` (default: `notifications-email-worker`)
- `KAFKA_AUTO_OFFSET_RESET` (default: `earliest`)

SMS (currently disabled):
- `KAFKA_EMAIL_WORKER_FORCE_SMS_DISABLED` (default: `true`)
- Twilio env vars are optional and unused until SMS is re-enabled.

## Ports

- Kafka (host): `9092`
- Kafka (internal): `19092`
- Worker: no inbound port

## Notes

- If using a Mailgun sandbox domain, the recipient must be authorized.
- The worker commits offsets only after requested channels succeed.
