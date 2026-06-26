---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S05'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---




# Update the workflow engine tests to Decision A semantics (targeted overdue admitted, closed-window FILE no longer aborts DEADLINE_PASSED)

## Scope

- `src/aeat/application/workflow/tests/test_engine.py`

## Description

- Update the workflow engine tests to Decision A semantics: a targeted overdue obligation is admitted with the extemporanea marker on the `COMPUTING_DEADLINES` step, and a closed-window FILE no longer aborts `DEADLINE_PASSED`.
- Preserve the never-existing-obligation refusal assertion (`NO_PENDING_OBLIGATION`).

## Outcome

Landed in commit `6e635f566`. `test_engine.py` 47/47 green; real-behaviour, no mocks/skips/xfail.

## Notes

