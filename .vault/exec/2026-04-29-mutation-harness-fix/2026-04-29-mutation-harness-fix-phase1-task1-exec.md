---
tags:
  - '#exec'
  - '#mutation-harness-fix'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-mutation-harness-fix-plan]]'
  - '[[2026-04-29-mutation-harness-fix-adr]]'
---

# exec phase1 task1 — generalise `_mutate_outer_sub_op` for clamp-wrapped chains

## What

`src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py` —
introduced a private `_swap_outer_sub_op_in_subtree` helper that
descends through `ClampPositiveFormula` wrappers until a `SubFormula`
is reached. `_mutate_outer_sub_op` now uses this helper, supporting
chains like Modelo 100 0545
(`clamp_pos(sub_op(sub_op(0432, 0445), 0455))`).

Two new harness-integrity tests:

- `test_mutate_outer_sub_op_descends_through_clamp_pos` — exercises
  the descent on M100 casilla 0545.
- `test_mutate_outer_sub_op_rejects_nonsubop_inside_clamp_pos` —
  asserts `clamp_pos(percent(...))` (M130 casilla 04) still raises
  `TypeError` rather than silently mis-mutating.

## Why

Issue #457 prescribes a sub_op fixture for M100 casilla 0545. Without
the descent step the helper raised `TypeError` on the
`ClampPositiveFormula` wrapper, blocking the prescribed scope.

## Verification

`uv run pytest src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py -q`
→ 60 passed (was 50 pre-#457).

Behaviour preserved on every direct `RoundFormula(SubFormula(...))`
case (existing tests unchanged).
