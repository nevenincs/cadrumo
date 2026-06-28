---
tags:
  - '#exec'
  - '#core-authority'
step_id: S05
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W02.P02.S05 — FilingValidationError -> CoreValidationError

## Change

Added `CoreValidationError` as explicit co-base of `FilingValidationError`.
Previous: `FilingValidationError(ModeloDraftError)`.
After: `FilingValidationError(ModeloDraftError, CoreValidationError)`.

MRO: FilingValidationError -> ModeloDraftError -> CoreValidationError
     -> CoreError -> AeatError -> ValueError -> Exception.

No catch sites exist for FilingValidationError in the codebase (it is only raised).

## Files touched

- `src/aeat/domain/filing/_errors.py`

## Verification gate

`pytest src/aeat/domain/filing/ -x -q` — 11 passed.

## Commit

`75d0cdddd` — feat(errors): W02.P02.S05 FilingValidationError -> CoreValidationError
