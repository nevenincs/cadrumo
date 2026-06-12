---
tags:
  - '#exec'
  - '#ledger-filter-period'
date: '2026-06-12'
step_id: 'S10'
related:
  - "[[2026-06-10-ledger-filter-period-plan]]"
---

# Write the period-continuity invariant test for adjacent quarter and month pairs across 2+ years

## Scope

- `src/aeat/application/aggregation/tests/test_period_continuity.py`

## Description

- Build an independent stdlib calendar oracle (`calendar.monthrange`) that derives quarter/month first and last days without calling `Period`, keeping the test non-tautological.
- Assert `Period` quarter/month `start_date` / `end_date` equal the oracle bounds across years `(2024, 2025, 2026)` — 2024 included to exercise the Feb-29 month end.
- Walk every adjacent quarter pair and adjacent month pair (including across the year boundary) and assert `prior.end_date + 1 day == next.start_date` and that no real calendar date is `contains`-ed by both periods.
- Cross-check that each quarter exactly covers its three constituent months with no slop.

## Outcome

Landed in commit `ce734ce57`. Verified green at HEAD (part of the 143-passed focused run). The anti-double-count invariant turns any future overlap/gap in the boundary computation into a loud failure.

## Notes

None.
