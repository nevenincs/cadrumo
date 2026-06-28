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

# exec phase2 task1 — expose per-class harness coverage generators

## What

- `src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py` — added
  `_iter_scalar_targets()` yielding
  `(ruleset_id, casilla_id, leaf_path)` for every mutated mul/div
  scalar leaf. Mirrors the unique target set behind
  `_build_test_params()`; the +1 % / -1 % directions count as one
  covered target.

- `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py` —
  added `_iter_percent_targets()` yielding
  `(ruleset_id, casilla_id, signature)` where `signature` is
  `f"literal:{path}"` for in-AST literal rates and
  `f"param:{param_id}"` for parameter-table rates.

- `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py` —
  added module-level constant `OUTER_SUB_OP_COVERAGE: tuple[tuple[str, str], ...]`
  enumerating every `(ruleset_id, target_casilla)` pair the harness
  exercises (including the M202 case from the dedicated test).
  `test_outer_sub_op_targets_match_parametrize_block` asserts the
  tuple stays in sync with the parametrize block.

## Why

The aggregator (`test_mutator_kill_rate.py`) needs to compute the
empirical kill-rate from the per-class harnesses. Pre-#457 the only
public interface was the parametrize fan-out; introspecting that
post-decoration is brittle and ty-unfriendly. The named generator /
constant pattern is explicit, importable, and stable.

## Verification

`uv run pytest src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py
src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py
src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py -q` → all
green.
