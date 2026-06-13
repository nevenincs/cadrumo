---
tags:
  - '#exec'
  - '#core-authority'
step_id: S06
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W02.P02.S06 — Application ValidationError family -> CoreValidationError

## Changes

Two application-layer ValidationError subclasses migrated to descend from CoreValidationError:

- `AggregationValidationError`: `(AggregationError, ValueError)` -> `(AggregationError, CoreValidationError)`
- `WizardValidationError`: `(WizardError)` -> `(WizardError, CoreValidationError)`

ExportFieldError (application/export) was already `CoreValidationError` — no change needed.
No application/filing ValidationError class exists.

## Verification gate

`pytest src/aeat/application/aggregation/ src/aeat/application/wizard/ -q --tb=no` — 485 passed.
1 pre-existing regex match failure in test_retenciones.py (translation key, unrelated).

## Commit

`28520e941` — feat(errors): W02.P02.S06 AggregationValidationError and WizardValidationError -> CoreValidationError
