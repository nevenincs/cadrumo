---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Keep the _data size-budget gate meaningful per distribution after the split so the budget is not evaded by moving bytes to the companion

## Scope

- `src/aeat/tests/test_data_size_budget.py`

## Description

- Update `test_data_size_budget.py` to keep the pre-existing 550 MiB total `_data` budget gate.
- Add per-distribution ceilings: a 230 MiB runtime-slice ceiling (measured ~173 MiB) and a 380 MiB companion-slice ceiling (measured ~312 MiB).
- Add an exhaustive-partition assertion so the split cannot silently move bytes out of the budgeted set to evade the gate.
- Commit `815efad31d`.

## Outcome

- 5/5 tests passed.

## Notes

No incidents. No skipped work.
