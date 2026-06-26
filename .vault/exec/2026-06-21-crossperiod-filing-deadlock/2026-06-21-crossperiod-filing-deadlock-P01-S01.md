---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S01'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---




# Re-scope the FILE-gate obligation schedule to the target period's filing year for an explicit FILE target, leaving the as-of-today projection on today.year

## Scope

- `src/aeat/application/workflow/_engine.py`

## Description

- Branch the `_stage_computing_deadlines` schedule resolution: for a `WorkflowPurpose.FILE` with an explicit `target_modelo`/`target_period` whose `filing_year != today.year`, call `self._deadline_engine.compute(profile, target_period.filing_year, today=today)` instead of `compute_obligation_schedule(today)`.
- Keep the common branch (and the as-of-today `pending_obligations` projection) on `today.year`, preserving the single-producer invariant.

## Outcome

Landed in commit `6e635f566`. A 2024 1T obligation is now found in the 2024 schedule under a 2026 clock and classified OVERDUE. `test_engine.py` 47/47 green; the as-of-today projection invariant is unchanged.

## Notes

