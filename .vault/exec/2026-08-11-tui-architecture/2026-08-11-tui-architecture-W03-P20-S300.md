---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:7d2c5014e565522b6303635fdf455c19eef19de9620ae0217b7811d4aaafb742'
step_id: 'S300'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop an absent work unit refusing with an instruction the operator cannot act on: the graded snapshot folds a missing work unit into the same CALCULATION_UNAVAILABLE refusal as a work unit that merely has no calculation, so the operator is told to calculate a work unit that does not exist, and the refusal contradicts the code's own documented meaning which names only the missing-calculation case; either route the absent target to TARGET_NOT_FOUND or widen the documented meaning and give the absent case its own actionable reconsideration text, then test that input, which no refusal test exercises today because both create their work unit first

## Scope

- `src/cadrumo/application/modelo/workspace.py graded-snapshot refusal branch`
- `workspace_models.py refusal-code documentation`
- `and a focused absent-work-unit refusal test`

## Changes

- `M` `src/cadrumo/application/modelo/workspace.py` -- split the folded `work_unit is None or work_unit.current_calculation_revision_id is None` branch into two: an absent work unit refuses `TARGET_NOT_FOUND` with an actionable "create a work unit for this target" reconsideration; an existing work unit with no calculation still refuses `CALCULATION_UNAVAILABLE`
- `M` `src/cadrumo/application/modelo/workspace_models.py` -- `TARGET_NOT_FOUND` gained a docstring naming the WORK selector's `ABSENT` state; `CALCULATION_UNAVAILABLE`'s docstring narrowed to state it fires only for an EXISTING work unit, and cross-references `TARGET_NOT_FOUND`
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py` -- new `test_resolve_graded_snapshot_result_refuses_target_not_found_when_no_work_unit_exists`
- `verify:` reachability traced through the real selector code, not assumed: `_select_natural_modelo_work_resolution` (`work_addressing.py`) returns `ModeloWorkResolution(state=ABSENT, work_unit=None, modelo=..., filing_year=..., period=...)` with no exception when no `WorkUnit` matches the natural coordinate -- the same `work_unit=None` case `resolve_static_inspection_result` already handles as a legitimate, non-refusing admission, confirming the branch in `resolve_graded_snapshot_result` is reachable
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py -q -m integration -n 0 -k "graded_snapshot_result_refuses"` -> `pass` (3 passed)

## Notes

Chose `TARGET_NOT_FOUND` over widening `CALCULATION_UNAVAILABLE`'s meaning: the
enum member already existed with zero production raisers and zero tests
anywhere in the tree, so adopting it here defines a clean, single-purpose
meaning rather than overloading one code to carry two distinct operator
remedies ("create a work unit" vs "calculate this work unit").
