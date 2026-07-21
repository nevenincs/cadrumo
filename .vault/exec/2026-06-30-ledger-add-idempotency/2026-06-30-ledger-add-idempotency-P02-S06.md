---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Confirm the keyless add path remains append-only so two genuine identical same-day movements both persist as distinct rows, and add a regression that locks this behaviour

## Scope

- `src/aeat/application/ledger/tests/`

## Description

- Add a real-repository regression proving two genuine identical same-day keyless movements both persist as distinct rows (append-only path preserved).

## Outcome

Landed in commit `3d8a6c14b`. The keyless path takes no idempotency guard, so genuine duplicates are never collapsed.

## Notes
