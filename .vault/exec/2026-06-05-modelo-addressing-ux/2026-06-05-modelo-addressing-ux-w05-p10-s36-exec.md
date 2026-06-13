---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S36'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W05.P10.S36 Final Residual Risk Matrix

Scope: persist final residual risks after modelo addressing and CLI decomposition execution.

## Description

- Measure `_modelo.py` at 2242 lines and lower its frozen size budget to 2242.
- Record that `_modelo.py` is no longer the original 4248-line monolith, but still contains residual command bodies for revision, verify, file, amendment, filing-record, verification-report, audit, root history, and reconcile surfaces.
- Record that centralized operator-addressing policy now lives in the application layer and is guarded against CLI bypass.
- Record broad size-guard residuals outside this slice: `_app_live.py` and `_ledger.py` exceed their frozen budgets in the shared worktree.
- Record that `_modelo_payloads.py` grew to 1240 lines because resume projection fields were added; its budget now matches the measured schema size.

## Outcome

Final residuals are explicit: modelo addressing policy is centralized and guarded, while remaining CLI decomposition debt is structural extraction work rather than hidden selector policy.

## Notes

The broad module-size guard remains red only for unrelated shared-worktree `_app_live.py` and `_ledger.py` growth.
