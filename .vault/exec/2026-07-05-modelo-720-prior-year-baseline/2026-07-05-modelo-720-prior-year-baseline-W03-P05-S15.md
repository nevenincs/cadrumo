---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S15'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

# Carry row-indexed mesh values into modelo draft and export replay without flattening them into scalar binding ids

## Scope

- `src/aeat/application/modelo/_calculation_resolution.py`

## Description

- Add a structured `row_binding_values` replay payload beside scalar `binding_overrides`.
- Persist row-indexed binding replay values on `CalculationRevision` and include them in the content hash.
- Rehydrate persisted row binding values as nested `binding_id -> row-index -> scalar` filing inputs.
- Pass source-mesh row binding values from bucket aggregation into modelo calculation persistence.
- Teach the filing draft builder the M720 row-field data types needed to materialize `ModeloBindingValue.row_index` without Decimal-coercing class, country, currency, identifier, or acquisition date values.
- Cover replay payloads and real M720 draft row materialization with focused tests.

## Outcome

- Row-indexed M720 mesh values now reach modelo draft replay without flattening row numbers into scalar binding ids.
- Revision identity changes when a row binding value changes, so row-only M720 filing content cannot drift under a stable calculation id.
- Filing replay returns nested row maps that `build_draft` converts into `ModeloBindingValue` records with `row_index`.
- Scalar `binding_overrides` remains free of M720 row binding ids.
- S16 enrollment remains untouched.

## Notes

- Gates: focused S15 pytest passed with 30 tests; scoped ruff check passed; scoped bytecode compilation passed.
- The step required narrow persistence and replay integrity wiring beyond the nominal helper module because draft/export replay cannot be honest if row values are only transformed locally and never stored.
- No new binding source kind, resolver convention, validator convention, or synthetic scalar binding id was introduced.
- Concurrent worktree WIP exists outside this step and was not edited or included in this step.
