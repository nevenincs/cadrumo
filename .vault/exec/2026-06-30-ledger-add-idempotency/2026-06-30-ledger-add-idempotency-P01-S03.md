---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Signal the no-op structurally on the result by returning the existing-row quintet with empty bucket_event_ids, preserving the uniform ledger mutation quintet shape

## Scope

- `src/aeat/application/ledger/_actions_common.py`

## Description

- Signal the idempotent no-op structurally by returning the existing row through the shared `_result` constructor with an empty `bucket_event_ids` tuple, preserving the uniform ledger mutation quintet (`bucket_id`, `transaction_id`, `bucket_event_ids`, `review_status`, `transaction`).
- An empty `bucket_event_ids` on a create result is the unambiguous no-op marker the CLI consumes (a real create always emits exactly one creation event).

## Outcome

Landed in commit `8349fc8b3`. The no-op reuses the existing quintet shape with no bespoke field, satisfying `ledger-mutation-returns-uniform-quintet`; the operator-facing info Notice is wired on the CLI envelope in `S04`.

## Notes

Code authored by a teammate and committed before this task was reassigned; this record documents the landed change.
