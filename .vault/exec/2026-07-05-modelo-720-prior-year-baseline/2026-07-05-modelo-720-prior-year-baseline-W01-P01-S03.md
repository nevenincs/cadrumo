---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S03'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---
# Clean stale threshold-axis authority comments so future workers do not reintroduce per-class semantics

## Scope

- `src/aeat/core/external_constants.py`

## Description

- Updated the `MODELO_720_REPORTING_THRESHOLD_EUR` comment to describe the threshold as per regulatory obligation block.
- Replaced the stale sentence that said an asset class is declarable by its own total with obligation-block aggregate semantics.

## Outcome

- The central threshold constant still provides the 50000.00 EUR value, but its documentation no longer conflicts with RD 1065/2007 block semantics.
- Focused ruff verification passed on the touched Python files.

## Notes

- No runtime constant value changed.
