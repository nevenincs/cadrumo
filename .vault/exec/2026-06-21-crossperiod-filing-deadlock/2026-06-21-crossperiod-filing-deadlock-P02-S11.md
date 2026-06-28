---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S11'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---




# Ratchet the owned _cross_period_clean_state.py SPLIT-CANDIDATE size budget from 1265 to 1300 for the feature addition

## Scope

- `src/aeat/tests/test_codebase_size_budgets.py`

## Description

- Bump the owned `_cross_period_clean_state.py` SPLIT-CANDIDATE size-budget ceiling from 1265 to 1300 to match the feature addition.

## Outcome

Landed in commit `84add274d`. `test_codebase_size_budgets.py` green; the module stays under its owned ratchet.

## Notes

