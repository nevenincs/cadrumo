---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S10'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# add an annual M100 actividad-económica income aggregator (annual window, actividad eligibility) mirroring the first-slice expense pipeline shape

## Scope

- `src/aeat/application/aggregation/`

## Description

Added an annual Modelo 100 actividad-económica income aggregator, the counterpart
of the M130 cumulative-quarter income path.

- `aggregate_renta_m100_income_ledger(_from_repositories)` in
  `src/aeat/application/aggregation/_renta_income_ledger.py`: full-ejercicio window
  (Jan 1 to Dec 31 of the period year), reuses `_classify_income_transaction`
  (same actividad eligibility, excludes nómina/personal), re-targets each eligible
  observation to the M100 income leaf 0171, and builds an M100 casilla aggregation.
- Rejects a non-annual period with `AggregationPeriodError`.

## Outcome

Unit tests in `test_renta_income_aggregation.py` cover the annual window (in-year
receipts summed into 0171, prior-year excluded) and the non-annual refusal; 21
income tests pass. The M130 quarterly path is untouched.

## Notes

None.
