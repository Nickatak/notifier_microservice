# Kafka Notifications for Appointment App

This project documents a simple, single-server Kafka setup for decoupled
notifications. The main app publishes appointment events; a notifications
service consumes them and sends email/SMS. Kafka stays private on the host.

## Portfolio Stack Description

Canonical system-wide architecture decisions and rationale live in the
`portfolio-frontend` repo:

`../portfolio-frontend/docs/architecture/repository-structure.md`

## Project status
- Phase: Kafka integration started (broker + producer + email-focused worker added).
- Canonical architecture doc: `docs/ARCHITECTURE.md`
- Feature scope checklist: `docs/FEATURE_SCOPE.md`

### Packaging status
- This repo itself is the reusable library package.
- The canonical Python package is `notifications` with adapters under
  `notifications/adapters/`.
- Distribution path: Git-based package install first, private registry later if
  needed.

### Reuse via Git install
Install the package directly from Git (no private PyPI server required):

```bash
pip install "kafka-notifications-lib @ git+ssh://git@github.com/<org>/<repo>.git@v0.1.0"
```

Pin to tags or commit SHAs for reproducible builds.

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
  - `domain/`
    - `email.py`: email channel rules
    - `sms.py`: SMS channel rules
  - `application/`
    - `process.py`: orchestration + aggregate success decision
  - `channels.py`: compatibility facade that re-exports the public functions
- `notifications/adapters/`:
  - reusable adapter modules (`payload`, `consumer_handler`, `kafka_runtime`,
    `real_senders`, `fake_senders`).
- `scripts/run_channel_demo.py` for local behavior checks without Kafka.
- `scripts/run_consumer_flow_demo.py` for Kafka-like record handling without Kafka.
- `scripts/publish_appointment_event.py` to publish a test
  `appointments.created` event to Kafka.
- `scripts/run_kafka_email_worker.py` to consume Kafka events and send email via
  Mailgun.
- `Dockerfile.worker` to package the Kafka email worker as a container image.
- `docker-compose.yml` to orchestrate broker, topic init, and worker services.
- `scripts/kafka_local_up.sh` to start a local Kafka broker and ensure topic
  creation.
- `scripts/kafka_local_down.sh` to stop/remove the local broker container.
- `scripts/kafka_local_status.sh` to inspect broker container status and topic list.
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
- Start local Kafka broker:
  - `bash scripts/kafka_local_up.sh`
- Check local Kafka status:
  - `bash scripts/kafka_local_status.sh`
- Stop local Kafka broker:
  - `bash scripts/kafka_local_down.sh`
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
- `KAFKA_TOPIC_APPOINTMENTS_CREATED_DLQ` (default: `appointments.created.dlq`)
- `KAFKA_GROUP_ID` (default: `notifications-email-worker`)
- `KAFKA_AUTO_OFFSET_RESET` (default: `earliest`)
- `KAFKA_POLL_TIMEOUT_SECONDS` (default: `1.0`)
- `KAFKA_MAX_RECORDS_PER_POLL` (default: `50`)
- `KAFKA_SEND_TIMEOUT_SECONDS` (default: `10`)
- `KAFKA_PRODUCER_ACKS` (default: `all`)
- `KAFKA_DLQ_ENABLED` (default: `true`)
- `KAFKA_DLQ_SEND_TIMEOUT_SECONDS` (default: `10`)
- `KAFKA_EMAIL_WORKER_FORCE_SMS_DISABLED` (default: `true`)

### Kafka quick start (email-first)
1. Start a broker.
   - Docker script (works with plain `docker`):
     - `bash scripts/kafka_local_up.sh`
   - Compose option (if `docker compose` is available):
     - `docker compose up -d kafka kafka-init`
2. Ensure `.env` contains `KAFKA_BOOTSTRAP_SERVERS=localhost:9092`.
3. Start the worker:
   - `python3 scripts/run_kafka_email_worker.py`
4. Publish a test event from another shell:
   - `python3 scripts/publish_appointment_event.py --email nickle87@gmail.com`
5. Optional status/teardown:
   - `bash scripts/kafka_local_status.sh`
   - `bash scripts/kafka_local_down.sh`

For now, the email worker forces `notify.sms=false` by default so you can keep
shipping email while Twilio toll-free verification is pending.

### Docker moving parts
1. `kafka` service:
   - Runs Apache Kafka broker in a container.
   - Exposes `9092` to your host.
2. `kafka-init` service:
   - One-shot container that creates `appointments.created` and
     `appointments.created.dlq` if missing.
   - Exits after topic setup.
3. `worker` service:
   - Built from `Dockerfile.worker`.
   - Runs `python3 scripts/run_kafka_email_worker.py`.
   - Uses `KAFKA_BOOTSTRAP_SERVERS=kafka:19092` because container-to-container
     traffic uses service names, not `localhost`.
   - On processing failure, publishes a DLQ envelope and commits source offset
     after DLQ publish succeeds.
4. Host publisher script:
   - `scripts/publish_appointment_event.py` usually runs on host and talks to
     `localhost:9092`.

### Compose run path
If `docker compose` is available on your machine:
1. Bring up broker + topic init + worker:
   - `docker compose up -d kafka kafka-init worker`
2. Publish from host:
   - `python3 scripts/publish_appointment_event.py --email nickle87@gmail.com`
3. See worker logs:
   - `docker logs -f notifications-email-worker`
4. Tear down:
   - `docker compose down`

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
