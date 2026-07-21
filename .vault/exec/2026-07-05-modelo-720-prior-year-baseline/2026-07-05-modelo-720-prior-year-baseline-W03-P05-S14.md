---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S14'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

# Return validated M720 row-indexed binding values from the foreign-assets aggregation resolver through the approved carrier

## Scope

- `src/aeat/application/aggregation/_foreign_assets.py`

## Description

- Capture the foreign-assets registry row resolver output instead of discarding it after validation.
- Return the validated row map through `CalculationSourceResolution.row_binding_values`.
- Extend resolver tests to prove the mesh carrier equals the registry row-value output and stays empty when a revision declares no foreign-asset source.
- Extend per-modelo M720 parity tests to prove the resolver carries the same row-indexed values as the prior aggregation path.

## Outcome

- The foreign-assets aggregation resolver now emits validated row-indexed M720 binding values through the approved S13 carrier.
- Scalar `binding_values` remains empty for these repeat-record fields, avoiding synthetic scalar ids.
- No new binding source kind, resolver convention, validator convention, or registry grouping was introduced.
- S15 can now project row-indexed mesh values into draft/export replay without needing to call the foreign-assets row resolver independently.

## Notes

- Gates: scoped ruff check passed; scoped bytecode compilation passed; focused sequential pytest passed with 50 tests.
- Concurrent worktree WIP exists outside this step and was not edited or included in this step.
