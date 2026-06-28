---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S04'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---




# Skip the submission filing-window preflight for the local FILE purpose alongside VERIFY

## Scope

- `src/aeat/application/workflow/_engine.py`

## Description

- Replace `skip_deadline_window=purpose is WorkflowPurpose.VERIFY` with `skip_window = purpose in (WorkflowPurpose.VERIFY, WorkflowPurpose.FILE)` on the submission preflight, since FILE is a LOCAL mark-as-filed that contacts AEAT zero times and its obligation existence is already enforced at the deadline stage.
- Document inline why re-applying the submission window gate would re-block the legitimate late local filing.

## Outcome

Landed in commit `6e635f566`. Fixes `test_verify_reaches_done_for_a_closed_filing_window`. The window gate now binds only an actual AEAT submission, which this app never performs.

## Notes

