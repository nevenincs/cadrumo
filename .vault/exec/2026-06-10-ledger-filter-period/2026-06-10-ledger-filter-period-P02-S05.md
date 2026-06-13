---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S05'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Add a test asserting aggregation_period_for_modelo raises on the deleted tokens and succeeds on every canonical StandardPeriodCode span member

## Scope

- `src/aeat/application/aggregation/tests/test_aggregation_period_for_modelo.py`

## Description

- Parametrise `test_canonical_span_token_maps_to_typed_period` over every span-shaped `StandardPeriodCode` member (instalment claves excluded) and assert each yields a `Period` for the filing year.
- Pin the three canonical shapes (quarter, annual, month) to their typed periods in `test_canonical_tokens_map_to_expected_typed_periods`.
- Assert every deleted alias (`Q1`-`Q4`, `A`, `ANUAL`, `ANNUAL`, `M01`-`M12`) now raises `AggregationValidationError` in `test_deleted_alias_tokens_now_raise`.
- Confirm lowercase canonical tokens still case-fold (not via an alias branch).

## Outcome

Landed in commit `9e20cfb44`. Verified green at HEAD (part of the 143-passed focused run). The regression guard fails the moment any deleted alias is reintroduced.

## Notes

None.
