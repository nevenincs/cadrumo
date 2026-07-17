---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---
# Clean stale threshold-axis enum documentation so raw classes are not described as independent floors

## Scope

- `src/aeat/core/aggregation.py`

## Description

- Updated the `ForeignAssetClass` docstring so it says each clave is declared separately while the threshold is applied to the containing regulatory obligation block.
- Left the enum members unchanged in this step.

## Outcome

- The enum documentation no longer says the 50000.00 EUR floor applies per raw class.
- Focused ruff verification passed on the touched Python files.

## Notes

- The official M720 class-code taxonomy issue remains open in Wave W02; this step deliberately did not change enum membership or code mapping.
