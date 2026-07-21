---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S21'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Upgrade the re-file of an already-PRESENTADO revision from the hard CalculationRevisionStateError to a clean idempotent no-op that returns the existing VIGENTE filing record without emitting a duplicate filing record or lifecycle event, keeping the not-VERIFICADO_COMPLETO case a hard refusal

## Scope

- `src/aeat/application/modelo/_filing_actions.py`

## Description

- Add a PRESENTADO branch in `file_modelo_revision` before the verified-state refusal: when the target revision is already filed, return its existing VIGENTE `ModeloRecord` via the new `_existing_vigente_filing_record` helper as a clean idempotent no-op - no new filing record, no duplicate `MODELO_FILED` event, no write/submit path touched (filing is local only per `aeat-safety-legal-gates`).
- Keep the not-VERIFICADO_COMPLETO case a hard `CalculationRevisionStateError`; a PRESENTADO revision with no VIGENTE record falls through to that refusal rather than fabricating a record.

## Outcome

Landed in commit `386618a68`. The no-op short-circuits before the workflow gate, so a re-file needs no auth provider; proven by `S23`.

## Notes

Co-committed with `S20`. The return type stays `ModeloRecord` (16 callers unchanged); the CLI detects the no-op from the resolved revision state (`S22`).
