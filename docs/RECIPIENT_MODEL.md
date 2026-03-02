# Recipient Model

## Who receives notifications?

All appointment notifications are sent to the **portfolio owner**, not the person who
booked the appointment. The owner's email is configured via the `NOTIFICATIONS_OWNER_EMAIL`
environment variable.

## Why?

This is a personal portfolio. When someone books an appointment through the calendar, the
owner needs to know — that's the whole point of the notification pipeline. Customer-facing
confirmations (e.g. "your appointment is booked") are a separate concern and not in scope
for this service.

## How contact info flows

1. The Kafka event contains `appointment.email` and `appointment.phone_e164` — these are
   the **booker's** contact details.
2. The payload adapter (`payload.py`) reads `NOTIFICATIONS_OWNER_EMAIL` from the
   environment and maps it to `notification_email` in the internal event dict.
3. The email domain module (`domain/email.py`) sends to `notification_email` (the owner)
   and includes the booker's contact info in the email body so the owner can follow up.

## Fallback behavior

If `NOTIFICATIONS_OWNER_EMAIL` is unset, the email falls back to `appointment.email`
(the booker's address). This keeps the pipeline functional during development but should
not be relied on in production — always set `NOTIFICATIONS_OWNER_EMAIL`.

## SMS channel

SMS notifications follow the same model: they go to the owner's configured phone number,
not the booker's. The booker's `phone_e164` is informational only.
