---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
step_id: 'S01'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Write a boundary-authority pin test asserting Period.contains() is the sole filter path for both the CLI and the calc engine

## Scope

- `src/aeat/application/aggregation/tests/test_period_boundary_authority.py`

## Description

- Add the boundary-authority pin module under `src/aeat/application/aggregation/tests/`.
- Pin `Period.contains` as the single public boundary predicate on `Period` via `test_no_parallel_contains_boundary_is_defined_on_period`, which fails if a second containment/within/covers/includes method is ever added.
- Drive the same `(year, AEAT-token)` input through the CLI command transport (`_canonical_period`), the CLI filter transport (`_filter_canonical_period`), and the calc-engine transport (`aggregation_period_for_modelo`).

## Outcome

Landed in commit `ce734ce57` (test(ledger-filter-period): pin single boundary authority + continuity invariant). Verified green at HEAD: the focused run of `test_period_boundary_authority.py`, `test_aggregation_period_for_modelo.py`, and `test_period_continuity.py` collected 143 items, 143 passed.

## Notes

The plan referenced the older `Period.start` / `Period.end` API; the landed module uses the current `Period.start_date` / `Period.end_date` fields and `Period.from_year_and_code`, reflecting the typed-`Period` refactor that landed in parallel. No behavioural divergence — the boundary is unchanged.
