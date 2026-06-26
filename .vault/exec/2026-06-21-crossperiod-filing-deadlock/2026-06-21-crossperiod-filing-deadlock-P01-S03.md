---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S03'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---




# Admit an explicitly-targeted overdue obligation as a late local filing, stamping the extemporanea marker on the COMPUTING_DEADLINES step details instead of aborting DEADLINE_PASSED

## Scope

- `src/aeat/application/workflow/_engine.py`

## Description

- In the `obligation.closes_on < today` branch, when `target_modelo`/`target_period` are present, append a successful `COMPUTING_DEADLINES` `WorkflowStep` carrying `overdue=true`/`extemporanea=true` plus the modelo/period/closes_on details, and `return obligation` instead of falling through to the `DEADLINE_PASSED` abort.
- Keep the non-targeted path on the original `DEADLINE_PASSED` abort.

## Outcome

Landed in commit `6e635f566`. The late LOCAL `work file` is admitted and persists the `app_filing` carry observation; `work file` contacts AEAT zero times. Reuses the existing registry-grounded `Recovery` (Ley 58/2003 art-27) admissibility. `test_deadline_passed_via_run_for_period` updated and green.

## Notes

