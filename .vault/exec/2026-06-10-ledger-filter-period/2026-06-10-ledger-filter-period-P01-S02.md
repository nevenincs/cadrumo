---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S02'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Assert that the CLI filter path and the calc-engine path both produce an identical Period object for the same (year, AEAT-token) input

## Scope

- `src/aeat/application/aggregation/tests/test_period_boundary_authority.py`

## Description

- Parametrise `test_cli_and_calc_engine_produce_an_identical_period` over years `(2024, 2025, 2026)` and every span-shaped `StandardPeriodCode` token (quarters, annual, months; instalment claves `1P`-`4P` excluded as span-less).
- Assert strict pydantic equality `command_period == filter_period == engine_period`, plus equal `start_date` / `end_date` and fully-closed `contains` on both bounds.
- Add `test_both_transports_route_through_one_period_boundary` walking every `(year, token)` pair to forbid a parallel boundary shape on either transport.

## Outcome

Landed in commit `ce734ce57`. Verified green at HEAD (143 passed in the focused three-module run). The two CLI transports and the calc-engine translator collapse to one identical `Period` object for every shared input, proving single-authority convergence.

## Notes

None.
