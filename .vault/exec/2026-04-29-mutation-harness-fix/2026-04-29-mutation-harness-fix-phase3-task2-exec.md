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

# exec phase3 task2 — M100 sub_op operand-swap fixtures

## What

`src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py`:

- Imported `MODELO_100_2024 / 2025 / 2026`.
- Added `_modelo_100_full_fixture()` — single asymmetric fixture
  exercising both prescribed M100 sub_op archetypes (0720 cuota
  diferencial direct chain + 0545 base liquidable general
  clamp-wrapped chain). Inputs:
  `0399=80 000`, `0445=20 000`, `0455=10 000`, `0699=2 000`,
  `0700=500`. Computed baselines: `0432=80 000`, `0545=50 000`,
  `0698=7 100,75`, `0720=4 600,75`. Verified identical for 2024 /
  2025 / 2026 (LIRPF arts. 17-20 + 63 unchanged across years).
- Added 6 `pytest.param` entries (2 archetypes × 3 years) to the
  parametrize block with descriptive ids
  (`modelo_100.{año}:casilla_0720_cuota_diferencial`,
  `modelo_100.{año}:casilla_0545_base_liquidable_general_clamp_wrapped`).
- Added `OUTER_SUB_OP_COVERAGE` module constant enumerating every
  covered `(ruleset_id, target_casilla)` pair (used by the
  kill-rate aggregator).
- Added `test_outer_sub_op_targets_match_parametrize_block` — sync
  invariant.

## Why

Issue #457 scope item 2 prescribes "≥ 1 sub_op operand-swap
fixture per M100 year" covering casilla 0720 (cuota diferencial,
direct sub_op chain) and casilla 0545 (base liquidable general,
clamp_pos-wrapped sub_op chain). 0545 requires the
`_swap_outer_sub_op_in_subtree` descent introduced in phase 1.

## Verification

`uv run pytest src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py -q`
→ 60 passed. Each M100 sub_op swap produces:

- 0720: baseline 4 600,75 € → mutated -4 600,75 €, delta 9 201,50 €.
- 0545: baseline 50 000 € → mutated 0 € (clamp absorbs negative),
  delta 50 000 €.

Both deltas exceed the 0.02 € floor by orders of magnitude.
