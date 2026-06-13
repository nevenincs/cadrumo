---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S04'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Delete the Q1-Q4, A, ANUAL, ANNUAL legacy alias branches from aggregation_period_for_modelo

## Scope

- `src/aeat/application/aggregation/_modelo_bindings.py`

## Description

- Remove the calendar-shape alias branches (`Q1`-`Q4`, `A`, `ANUAL`, `ANNUAL`, and the `M01`-`M12` month-prefixed forms) from `aggregation_period_for_modelo`.
- Reduce the translator body to: case-fold the token, resolve via `Period.from_year_and_code`, and reject any token that is not a span-shaped canonical AEAT code, per `no-legacy-compatibility` (deleted outright, no bridge).

## Outcome

Landed in commit `9e20cfb44` (refactor(ledger-filter-period): delete legacy period aliases from aggregation_period_for_modelo (P02)). Verified at HEAD: `git grep -E '"Q1"|"Q2"|"Q3"|"Q4"|"ANUAL"|"ANNUAL"' -- src/aeat/application/aggregation/_modelo_bindings.py` returns no matches (exit 1, clean). The translator now accepts only `1T`-`4T`, `0A`, `01`-`12`.

## Notes

None.
