---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:6507b9a7a69577afd3702f0f5f09cf4c93e5ac52b39e76ceebe77ce92c22979b'
step_id: 'S23'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Add real-repository tests proving a retried file of a PRESENTADO revision returns the existing record as a no-op with no duplicate record or event while a not-yet-verified file still hard-refuses

## Scope

- `src/aeat/application/modelo/tests/`

## Description

- Add `test_file_flow_filing_idempotent.py` exercising the real `file_modelo_revision` path against the real registry and encrypted repositories.
- Prove a re-file of a PRESENTADO revision returns the existing record (same `filing_record_id`, `filed_at` unchanged, not re-stamped to the retry clock), persists no duplicate filing record, emits exactly one `MODELO_FILED` event, and leaves the revision PRESENTADO.
- Prove a BORRADOR (not VERIFICADO_COMPLETO) revision still hard-refuses with `CalculationRevisionStateError`.

## Outcome

Landed in commit `cdad9bc22`; 2 tests pass. Reuses the file-flow support helpers so the setup is the same real verify-then-file path the existing suite exercises.

## Notes

No mocks. The re-file asserts the bucket-event `MODELO_FILED` count stays one, the strongest structural proof that no second lifecycle event was emitted.
