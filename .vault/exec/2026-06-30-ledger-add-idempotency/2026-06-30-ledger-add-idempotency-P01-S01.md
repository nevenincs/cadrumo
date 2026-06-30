---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S01'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---




# Add an existence check in create_manual_transaction so a same-key add whose content matches the stored row returns the existing-row quintet as a no-op, emitting no second LEDGER_TRANSACTION_CREATED event, leaving created_at and modified_at unchanged, and skipping evidence re-verification, modelled on create_work_unit

## Scope

- `src/aeat/application/ledger/_actions_manual.py`

## Description

- Move the catalogue load to the top of `create_manual_transaction` and add a guarded existence check before any event build.
- When `idempotency_key` is supplied and the derived id names an already-stored row whose content matches `_command_matches_current`, return the stored row unchanged with no second `LEDGER_TRANSACTION_CREATED` event, no `created_at` / `modified_at` re-stamp, and no evidence re-verification, mirroring the `create_work_unit` existing-record contract.

## Outcome

Landed in commit `8349fc8b3` (`feat(ledger): make keyed manual add a guarded-idempotent no-op (P01.S01-S03)`). A retried keyed add resolves to the deterministic clock-free id and returns the existing row; the keyless path is untouched and stays append-only.

## Notes

Code authored by a teammate and committed before this task was reassigned; this record documents the landed change. The matching unit/roundtrip proofs land under Phase `P05`.
