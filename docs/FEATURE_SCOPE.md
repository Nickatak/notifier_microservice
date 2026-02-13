# Feature Scope (MVP vs Later)

This document locks feature scope before implementation.
Date finalized: 2026-02-13.

## Scope rules
- `MVP` means required before first production-like demo.
- `Later` means intentionally deferred.
- Any new feature request must be classified into one of these two buckets.

## Provider status notes
- 2026-02-13: Mailgun email live-send test succeeded.
- 2026-02-13: Twilio account upgraded to paid and toll-free verification
  submitted.
- 2026-02-13: SMS live-send validation is paused pending toll-free verification
  approval.

## MVP must-have checklist

### Eventing and contract
- [ ] Use one Kafka topic: `appointments.created`.
- [ ] Publish one event per appointment creation.
- [ ] Event includes `notify.email` and `notify.sms` boolean flags.
- [ ] At least one channel flag is true per event.
- [ ] Event includes `appointment.email` when `notify.email=true`.
- [ ] Event includes `appointment.phone_e164` when `notify.sms=true`.
- [ ] Event includes unique `event_id` for deduplication.

### Notification channels
- [ ] Email channel sends when `notify.email=true`.
- [ ] SMS channel sends when `notify.sms=true`.
- [ ] If both flags are true, both channels are attempted for the same event.
- [ ] Channel-specific success/failure is logged with `event_id`.

### Processing semantics and reliability
- [ ] Delivery model is at-least-once.
- [ ] Consumer commits offset only after all requested channels succeed.
- [ ] Retries are enabled for transient provider failures.
- [ ] Retry policy is defined and implemented (attempt count + backoff).
- [ ] Consumer crash before commit causes re-delivery on restart.

### Idempotency and duplicate protection
- [ ] Deduplicate by `event_id + channel`.
- [ ] Duplicate event reprocessing does not send duplicate notifications.

### Observability and operations
- [ ] Structured logs include `event_id`, channel, and result.
- [ ] Metrics include produced, consumed, email success/failure, sms success/failure.
- [ ] Basic health endpoint/check for notifications worker.

### Security and deployment
- [ ] Kafka is private-only (localhost or private Docker network).
- [ ] Secrets loaded from environment variables.
- [ ] No public Kafka exposure.

## Later (explicitly out of MVP)
- DLQ topic and replay tooling UI.
- Additional channels (push, WhatsApp, voice).
- Appointment reschedule/cancel/reminder event types.
- Multi-broker HA and replication > 1.
- Outbox pattern for DB/event atomicity.
- Advanced rate limiting and tenant-level controls.
- Provider failover across multiple SMS/email vendors.
- Extract reusable adapters (Kafka + provider transport layer) into a standalone
  shared Python package for cross-project reuse.

## MVP done definition
- Every item in `MVP must-have checklist` is implemented and validated.
- Architecture decisions in `docs/ARCHITECTURE.md` remain consistent.
