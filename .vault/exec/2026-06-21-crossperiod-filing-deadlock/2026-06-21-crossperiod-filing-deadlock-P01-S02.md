---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S02'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---




# Guard the target-year compute against NoDeadlineWindowsError so a year with no registry windows degrades to NO_PENDING_OBLIGATION rather than UNHANDLED_EXCEPTION

## Scope

- `src/aeat/application/workflow/_engine.py`

## Description

- Wrap the target-year `compute` in `try/except NoDeadlineWindowsError`, falling back to the as-of-today schedule so a target filing year with no registry windows degrades to `NO_PENDING_OBLIGATION` at the absent-target filter rather than `UNHANDLED_EXCEPTION`.
- Import `NoDeadlineWindowsError` from `...domain.deadlines`.

## Outcome

Landed in commit `6e635f566`. Fixes `test_gate_aborts_when_projection_lacks_the_target`; a never-existing obligation still refuses `NO_PENDING_OBLIGATION`.

## Notes

