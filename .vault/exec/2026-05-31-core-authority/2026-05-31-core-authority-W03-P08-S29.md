---
tags:
  - '#exec'
  - '#core-authority'
step_id: S29
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P08.S29 — Rename ERROR_CODES to OperatorSurfaceErrorCodes (RENAME-009)

## Change

Renamed `ERROR_CODES` to `OperatorSurfaceErrorCodes` in
`src/aeat/application/operator_surface/_contract.py` (declaration + 1 use in
`build_operator_surface_contract`). No external callers import this constant
from outside the operator_surface package.

## Verification gate

`pytest src/aeat/application/operator_surface/test_contract.py -q -k "not test_require_accepted_root_uses_registered_application_error"`
— 13 passed, 0 failed. The excluded test is a pre-existing failure (locale
mismatch in regex match — Spanish error message vs. English regex pattern).

## Commit

`56b77a807` — refactor(aggregation): rename ERROR_CODES to AggregationErrorCodes and OperatorSurfaceErrorCodes (RENAME-009)
