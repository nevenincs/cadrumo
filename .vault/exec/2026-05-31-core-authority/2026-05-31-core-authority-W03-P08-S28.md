---
tags:
  - '#exec'
  - '#core-authority'
step_id: S28
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P08.S28 — Rename ERROR_CODES to AggregationErrorCodes (RENAME-009)

## Change

Renamed `ERROR_CODES` to `AggregationErrorCodes` in:
- `src/aeat/application/aggregation/_service.py` (declaration + `__all__` + 1 use)
- `src/aeat/application/aggregation/__init__.py` (import + `__all__`)
- `src/aeat/application/aggregation/test_per_modelo_service.py` (import + assertion)

## Verification gate

`pytest src/aeat/application/aggregation/test_per_modelo_service.py -q`
— 11 passed, 0 failed.

## Commit

`56b77a807` — refactor(aggregation): rename ERROR_CODES to AggregationErrorCodes and OperatorSurfaceErrorCodes (RENAME-009)
