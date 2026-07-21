---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---
# Clean stale threshold-axis row-binding comments so registry helpers point to obligation-block semantics

## Scope

- `src/aeat/domain/calculations/registry/_detail_record_bindings.py`

## Description

- Updated the Modelo 720 foreign-asset row-binding comment to describe the 50000.00 EUR threshold as per regulatory obligation block.
- Left the row-binding resolver behavior unchanged; it still resolves already-selected row observations into row-indexed binding values.

## Outcome

- Registry helper comments no longer conflict with the application-layer block threshold gate.
- Focused ruff verification passed on the touched Python files.

## Notes

- The row-indexed source-mesh carrier remains open in Wave W03.
