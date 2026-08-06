---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:743510d626e70228c12065e7ed24ef51c4ca0a8690a50822b33e66cfa37685d2'
step_id: 'S13'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

# Add the approved row-indexed M720 carrier to the calculation source resolution envelope

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Add `row_binding_values` to `CalculationSourceResolution` as a typed, 1-based `(binding_id, row_index)` carrier for registry row values.
- Validate row indexes and freeze row-binding values deterministically for replay-safe source resolution state.
- Serialize row-binding coordinates as JSON-safe objects with value-kind tags instead of tuple keys.
- Merge row-binding values through exclusive and precedence source-resolution paths while detecting duplicate ownership by full row coordinate.
- Extend source-mesh tests for serialization, JSON replay validation, invalid serialized row indexes, invalid serialized decimal row values, empty readiness responses, merge carry-through, and duplicate row-coordinate ownership.

## Outcome

- The source mesh can now carry row-indexed M720 binding values without synthetic scalar ids and without overloading detail-row DTOs.
- JSON replay preserves numeric-looking text row values, such as asset identifiers, while restoring tagged Decimal row values.
- Merge semantics remain exclusive by resolver-owned coordinate, preserving the existing source-mesh conflict model.
- The change adds no new binding source kind, resolver convention, validator convention, or registry grouping.
- This unlocks the foreign-assets resolver enrollment work in the next row-carrier steps.

## Notes

- Gates: scoped ruff check passed; scoped bytecode compilation passed; locale scaffold and audit passed; scoped source-mesh pytest passed with 27 tests.
- Concurrent worktree WIP exists outside this step and was not edited or included in this step.
