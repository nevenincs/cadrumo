---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-08'
step_id: 'S13'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Add a real-repository idempotency test proving a retried keyed add yields one row, one creation event, an unchanged created_at, and a no-op notice

## Scope

- `src/aeat/application/ledger/tests/`

## Description

- Add real-repository proofs that a retried keyed add yields exactly one row, one `LEDGER_TRANSACTION_CREATED` event, an unchanged `created_at`, and the empty-`bucket_event_ids` no-op signal; plus 3+ retries and an interleaved retry through a fresh repo over the same store.

## Outcome

Landed in commit `3d8a6c14b`. No mocks; drives `create_manual_transaction` against a real encrypted `SecureObjectRepository`. The interleaved case cites the single-writer load-modify-save upsert path.

## Notes
