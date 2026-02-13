# High-Level Architecture (v1)

This document defines the baseline architecture before implementation.
Date finalized: 2026-02-13.
MVP feature boundary: `docs/FEATURE_SCOPE.md`.

## Goals
- Decouple appointment creation from notification delivery.
- Keep Kafka private (single server or private Docker network).
- Demonstrate reliable, replayable event processing for portfolio value.
- Support dual-channel notifications (email and SMS) for MVP.

## Non-goals (v1)
- Multi-region or multi-broker high availability.
- Public Kafka endpoints.
- Exactly-once end-to-end semantics.
- Extracting reusable adapters into a standalone shared package (post-MVP).

## System context
- Frontend: NextJS submits appointment requests.
- API: Django writes appointments to Postgres and publishes Kafka events.
- Messaging: Kafka (KRaft mode) stores and serves events.
- Worker: Notifications service consumes events and sends email and/or SMS.

## Component responsibilities
- `NextJS`: user interaction and API calls.
- `Django API`: appointment validation, DB write, event publish.
- `Postgres`: source of truth for appointments.
- `Kafka Broker`: durable event log for decoupling and replay.
- `Notifications Service`: consume, send requested channels, commit on success.
- `Email Provider`: external email delivery service.
- `SMS Provider`: external SMS delivery service.

## Kafka topology (v1)
- Mode: KRaft (no ZooKeeper).
- Broker count: 1.
- Topic: `appointments.created`.
- Partitions: 1 (simple ordering and minimal ops overhead for v1).
- Replication factor: 1 (single-server constraint).
- Retention: 7 days (can be tuned later).

## Event contract: `appointments.created`
JSON payload shape:

```json
{
  "event_id": "uuid",
  "event_type": "appointments.created",
  "occurred_at": "2026-02-13T17:00:00Z",
  "notify": {
    "email": true,
    "sms": true
  },
  "appointment": {
    "appointment_id": "uuid-or-int",
    "user_id": "uuid-or-int",
    "time": "2026-02-20T15:00:00Z",
    "email": "user@example.com",
    "phone_e164": "+15555550123"
  }
}
```

Contract rules:
- `event_id` is unique per emitted event.
- At least one channel flag must be true: `notify.email` or `notify.sms`.
- `appointment.appointment_id` is required and stable.
- `appointment.email` is required when `notify.email=true`.
- `appointment.phone_e164` is required when `notify.sms=true`.
- Consumers must ignore unknown fields to allow additive schema changes.

## Delivery and processing semantics
- Delivery model: at-least-once.
- Producer ack level: wait for broker ack before treating publish as success.
- Consumer commit strategy: commit offset only after all requested channel sends
  succeed for that event.
- Retry behavior: retry transient provider failures before giving up processing.

## Idempotency strategy
- Duplicate events are possible with at-least-once delivery.
- Notifications service should deduplicate using `event_id + channel`.

## Failure model (v1)
- If consumer crashes before commit, Kafka re-delivers on restart.
- If either provider is down for a requested channel, consumer retries and does
  not commit until requested channel delivery succeeds.
- If Django writes DB row but publish fails, record this in logs and return an
  application error; outbox pattern is a future hardening step.

## Security posture
- Kafka is bound to localhost or private Docker network only.
- No public ingress to Kafka.
- Secrets and credentials are sourced from environment variables.
- Optional hardening: SASL/SCRAM and ACLs after baseline flow works.

## Observability baseline
- Structured logs from producer and consumer, including `event_id`.
- Track at minimum:
  - produced event count
  - consumed event count
  - email success/failure count
  - sms success/failure count
  - consumer lag (when available)

## Implementation phases
1. Infrastructure
   - Add Docker Compose for Kafka (KRaft) and optional UI tools.
   - Create topic `appointments.created`.
2. Producer path
   - Add Django Kafka producer on appointment creation.
   - Include event schema and validation.
3. Consumer path
   - Add notifications worker consuming `appointments.created`.
   - Send requested channel(s) from `notify` flags.
   - Commit offsets only after all requested channels succeed.
4. Hardening
   - Add retries, idempotency guard, and better metrics/logging.
   - Evaluate outbox pattern if DB/event atomicity risk is unacceptable.
5. Reuse extraction (post-MVP)
   - Move reusable Kafka/provider adapter code into a standalone package.
   - Keep domain/application business rules in service repos.
   - Version shared adapter APIs and event helpers semantically.

## Definition of done for architecture phase
- Topic naming is consistent: `appointments.created`.
- Single-server private Kafka model is documented.
- Event contract and delivery semantics are documented.
- Channel flags are documented for dual-channel MVP (`email`, `sms`).
- Implementation phases are agreed and sequenced.
