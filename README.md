# Kafka Notifications for Appointment App

This project documents a simple, single-server Kafka setup for decoupled
notifications. The main app publishes appointment events; a notifications
service consumes them and sends email/SMS. Kafka stays private on the host.

## Project status
- Phase: Kafka integration started (producer + email-focused worker added).
- Canonical architecture doc: `docs/ARCHITECTURE.md`
- Feature scope checklist: `docs/FEATURE_SCOPE.md`

### Future extraction intent
- After MVP is stable, extract reusable Kafka transport/adapters from this repo
  into a separate shared Python package (PyPI-style internal package).
- Keep app-specific business logic in each service repo, and share only generic
  transport/config/retry/serialization adapter code.

### Provider rollout notes
- 2026-02-13: Mailgun email live-send test succeeded.
- 2026-02-13: Twilio account upgraded from trial to paid.
- 2026-02-13: Twilio toll-free verification was submitted for the project SMS
  sender number.
- 2026-02-13: SMS live testing is temporarily shelved until toll-free
  verification is approved (Twilio can accept API requests while final delivery
  is blocked/pending compliance).

## Current implementation
- Layered module layout in `notifications/`:
  - `adapters/`
    - `payload.py`: payload -> event dict normalization
    - `fake_senders.py`: local sender adapters
    - `real_senders.py`: Mailgun email + Twilio SMS adapters
    - `consumer_handler.py`: controller-like message handling + commit decision
  - `domain/`
    - `email.py`: email channel rules
    - `sms.py`: SMS channel rules
  - `application/`
    - `process.py`: orchestration + aggregate success decision
  - `channels.py`: compatibility facade that re-exports the public functions
- `scripts/run_channel_demo.py` for local behavior checks without Kafka.
- `scripts/run_consumer_flow_demo.py` for Kafka-like record handling without Kafka.
- `scripts/publish_appointment_event.py` to publish a test
  `appointments.created` event to Kafka.
- `scripts/run_kafka_email_worker.py` to consume Kafka events and send email via
  Mailgun.
- `tests/test_channels.py` for channel/dispatch unit coverage.
- `tests/test_consumer_handler.py` for commit/no-commit handler behavior.
- `tests/test_real_senders.py` for Mailgun/Twilio adapter behavior.

### Local checks
- Run demo:
  - `python3 scripts/run_channel_demo.py`
- Run consumer-flow demo:
  - `python3 scripts/run_consumer_flow_demo.py`
- Run Kafka email worker:
  - `python3 scripts/run_kafka_email_worker.py`
- Publish Kafka test event:
  - `python3 scripts/publish_appointment_event.py --email you@example.com`
- Run tests:
  - `python3 -m unittest discover -s tests -p 'test_*.py'`

### Real sending adapters
- Email sender: `send_email_via_mailgun_from_env`
- SMS sender: `send_sms_via_twilio_from_env`

Quick setup:
- Copy template: `cp .env.example .env`
- Fill real credentials in `.env`
- Install Python deps: `pip install -r requirements.txt`

Required env vars for Mailgun:
- `MAILGUN_API_KEY`
- `MAILGUN_DOMAIN`
- `MAILGUN_FROM_EMAIL`

Optional Mailgun env vars:
- `MAILGUN_API_BASE_URL` (default: `https://api.mailgun.net`)
- `MAILGUN_TIMEOUT_SECONDS` (default: `10`)

Required env vars for Twilio:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_PHONE`

Optional Twilio env vars:
- `TWILIO_API_BASE_URL` (default: `https://api.twilio.com`)
- `TWILIO_TIMEOUT_SECONDS` (default: `10`)

Required env vars for Kafka:
- `KAFKA_BOOTSTRAP_SERVERS` (example: `localhost:9092`)

Optional Kafka env vars:
- `KAFKA_TOPIC_APPOINTMENTS_CREATED` (default: `appointments.created`)
- `KAFKA_GROUP_ID` (default: `notifications-email-worker`)
- `KAFKA_AUTO_OFFSET_RESET` (default: `earliest`)
- `KAFKA_POLL_TIMEOUT_SECONDS` (default: `1.0`)
- `KAFKA_MAX_RECORDS_PER_POLL` (default: `50`)
- `KAFKA_SEND_TIMEOUT_SECONDS` (default: `10`)
- `KAFKA_PRODUCER_ACKS` (default: `all`)
- `KAFKA_EMAIL_WORKER_FORCE_SMS_DISABLED` (default: `true`)

### Kafka quick start (email-first)
1. Start your Kafka broker and ensure `KAFKA_BOOTSTRAP_SERVERS` points to it.
2. Start the worker:
   - `python3 scripts/run_kafka_email_worker.py`
3. Publish a test event from another shell:
   - `python3 scripts/publish_appointment_event.py --email nickle87@gmail.com`

For now, the email worker forces `notify.sms=false` by default so you can keep
shipping email while Twilio toll-free verification is pending.

Example (swap console senders for real adapters in handler call):
```python
from notifications.adapters.consumer_handler import handle_message
from notifications.adapters.real_senders import (
    send_email_via_mailgun_from_env,
    send_sms_via_twilio_from_env,
)

result = handle_message(
    record,
    send_email=send_email_via_mailgun_from_env,
    send_sms=send_sms_via_twilio_from_env,
    commit=commit_callback,
    reject=reject_callback,
)
```

## Why Kafka here
- Clean separation between appointment creation and notification sending.
- Reliable delivery with retries and replay.
- Portfolio-friendly architecture without extra public surface area.
- Multi-channel notification support (email + SMS) from one event stream.

## High-level flow
1. Django creates an appointment in the database.
2. Django publishes an event to Kafka topic `appointments.created`.
3. Notifications service consumes the event.
4. Notifications service sends email and/or SMS based on event channel flags.
5. Consumer commits the offset after all requested channels succeed.

## Minimal deployment model (single server)
- Kafka broker runs locally (or on a private Docker network).
- Django app runs as producer.
- Notifications worker runs as consumer.
- Kafka is not exposed to the public internet.

## Security posture (simple + credible)
- No API keys needed (only internal services talk to Kafka).
- Keep Kafka bound to `127.0.0.1` or private Docker network.
- Optional: enable SASL/SCRAM + ACLs to show auth intent.
- Secrets live in environment variables.

## Kafka parts explained (what runs the show)

### Broker
The Kafka server process. It:
- Accepts writes from producers.
- Stores events on disk.
- Serves reads to consumers.
- Tracks topic metadata and partition leadership.

### Topic
A named stream of events, e.g. `appointments.created`.
Topics are split into partitions for scalability.

### Partitions are not subtopics
Partitions are internal slices of a topic, not separate named channels.
You subscribe to the topic (e.g. `appointments.created`), and Kafka
assigns partitions of that topic to consumers in the same group.

### Partition
An ordered, append-only log inside a topic.
Events are written in order and assigned a monotonically increasing offset.

### Offset
The position of a record in a partition.
Consumers store their offsets so they can resume or replay.

### Producer
Your Django app. It sends events to a topic.
Kafka acknowledges writes so you can confirm delivery.

### Consumer
Your notifications service. It reads events from a topic.
It commits offsets after successful processing of requested channels.

### Consumer Group
Multiple consumers sharing the work.
Kafka ensures each partition is processed by only one consumer in the group.

### Metadata / Controller
Kafka needs to know which broker owns which partition.
In older setups, Zookeeper tracked this metadata.
In modern Kafka, the controller handles it directly (KRaft mode).

### Log segments + retention
Kafka stores data in files on disk (segments).
Retention policies decide how long events are kept.
This allows replay when needed.

## Under the hood (what keeps track of topics and delivery)
- When a producer writes, the broker appends to a partition log.
- The broker assigns offsets and confirms write durability.
- Consumers poll for new records.
- Kafka does not "push alerts" by default; consumers pull.
- Kafka stores consumer offsets so it knows what has been read.

## Kafka terminology (quick answers)
- Broker: the Kafka server process.
- Topic: the named stream you publish/subscribe to.
- Partition: an internal shard of a topic, not a separate subtopic.
- Consumer group: a set of consumers that share work for a topic.
- Offset: a per-partition index; consumers store their last processed offset.
- Polling: Kafka clients use a TCP protocol to fetch records (not HTTP).
- Metadata: the broker/controller stores topic/partition layout and leaders.

## Example request cycle (appointment creation to notifications sent)
1. User submits appointment form in NextJS.
2. NextJS calls Django API to create the appointment.
3. Django validates and writes the appointment to the DB.
4. Django publishes event to topic `appointments.created` with payload:
   `{ appointment_id, user_id, time, email, phone_e164, notify: { email, sms } }`
5. Notifications service consumes the event from `appointments.created`.
6. Notifications service sends email and/or SMS per `notify` flags.
7. Consumer commits offsets after requested channel deliveries succeed.

## Diagram (end-to-end flow)
```text
User
  |
  v
NextJS (UI)
  |
  v
Django API  ----writes---->  Postgres
  |
  | produce event: appointments.created
  v
Kafka Broker
  | (topic: appointments.created)
  v
Notifications Service
  ----sends---->  Email Provider
  ----sends---->  SMS Provider
```

## Practical setup goals
- 1 topic: `appointments.created`
- 1 producer: Django app
- 1 consumer: Notifications service
- 2 channels in MVP: email + SMS
- Private network only
