---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S34'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
---

# `cross-period-filing-clean-state` `W03.P08.S34` exec - Modelo 303 carry-forward clean-state requirements

## Description

Verified Modelo 303 carry-forward dependencies are included in the filing-grade clean-state workflow coverage.

## Outcome

The workflow enforcement test covers Modelo 303 period `2T` and asserts filing is refused when the prior-period carry-forward source is not clean.

## Notes

The test path is `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py` and uses real work units, calculation revisions, and repositories.
