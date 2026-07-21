---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-08'
step_id: 'S15'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Add a test proving a deliberate duplicate stays possible via the keyless path and via a distinct idempotency key, both yielding two distinct rows

## Scope

- `src/aeat/application/ledger/tests/`

## Description

- Add real-repository tests proving a deliberate duplicate stays possible via two distinct idempotency keys and via the keyless path, each yielding two distinct rows.

## Outcome

Landed in commit `3d8a6c14b`. Confirms the idempotency guard never collapses genuinely-distinct movements.

## Notes
