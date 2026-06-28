---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S04'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P01.S04 explicit work-unit ID validation

Scope:
- `src/aeat/application/modelo/_selectors.py`

## Description

- Support exact `work_unit_id` selection as an advanced escape hatch.
- Validate any supplied bucket, modelo, filing year, period, or registry revision flags against the loaded exact work unit.
- Refuse contradictions with a typed selector contradiction error.

## Outcome

Raw work-unit IDs remain available for exact addressing, but they cannot be combined with contradictory natural-key flags silently.

## Notes

- Tests cover explicit-ID contradiction against the filing-year axis.
