---
tags:
  - '#exec'
  - '#mutation-harness-fix'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-mutation-harness-fix-plan]]'
  - '[[2026-04-29-mutation-harness-fix-adr]]'
  - '[[2026-04-29-mutation-harness-fix-phase1-summary-exec]]'
---

# Phase summary — `mutation-harness-fix` Wave 1-4 (zero-deferred coverage)

## Result

Drove the issue-#457 fix to **100 % coverage**: every populated
`SubFormula` and Mul/Div literal leaf across every landed ruleset is
now exercised by the per-class harness. The deferred catalogue
totals are zero.

Tests delta (mutation harness suite): 188 (pre-#457) → 568
(post-Wave-2). 1 144 tests across the full `_rulesets/` package
green. Full project suite: 4 555 passed, 14 skipped, 24 deselected,
0 unexpected failures (1 pre-existing flaky test in
`src/aeat/entrypoints/cli/workflow/test_cli.py` excluded — unrelated to this PR
and reproduces on a stash --keep-index of the pre-#457 worktree).
Coverage: 80.52 % on `src/aeat`. Lint / typecheck / hooks all green.

## Wave 1 — operand-swap path-based generalisation

`test_operand_swap_mutation.py`:

- Added `_mutate_sub_op_at_path(ruleset, casilla, sub_op_path)`
  generalising the outer-only mutator to target any
  :class:`SubFormula` descendant.
- Added `_walk_sub_op_paths(formula)` enumerator that yields every
  `SubFormula` path in operand-index order.
- Replaced the literal `@pytest.mark.parametrize` block (~250 LoC,
  hand-maintained per-target) with a programmatic
  `_build_sub_op_test_params()` that walks `_SUB_OP_COVERAGE_DATA`
  and emits one parametrize entry per `(ruleset, casilla, path)`
  triple.
- `_SUB_OP_COVERAGE_DATA` is the new single-source-of-truth for
  sub_op coverage; `SUB_OP_COVERAGE` (consumed by the kill-rate
  aggregator) is derived from it via `_build_sub_op_coverage()`.
- Retired the dedicated M202 outer-only test (M202 now appears in
  `_SUB_OP_COVERAGE_DATA` like every other ruleset and the walker
  yields all 3 sub_op paths automatically).
- Retired the
  `test_outer_sub_op_targets_match_parametrize_block` sync invariant
  (no longer needed — both consumers now derive from the same data).
- Added 3 new harness-integrity tests:
  `test_mutate_sub_op_at_path_rejects_non_sub_formula_node`,
  `test_mutate_sub_op_at_path_rejects_missing_casilla`,
  `test_walk_sub_op_paths_yields_every_subformula_descendant`.

## Wave 2 — comprehensive M100 fixtures

`test_operand_swap_mutation.py`:

- Replaced the 8-input `_modelo_100_full_fixture` with two
  comprehensive fixtures:
  - `_modelo_100_full_fixture_2024()` — drives every B1 / B2 / C /
    D normal / D simplificada / D modulos / E / F / G / N chain to
    asymmetric operand pairs; provides 0540 / 0542 / 0550 / 0560 /
    0595 / 0698 / 0720 baselines for the 2024 ahorro top-bracket
    rate (0.14 pre-Ley-7/2024).
  - `_modelo_100_full_fixture_post_2025()` — same shape with the
    post-Ley-7/2024 0.15 ahorro top-bracket rate; baselines lift by
    Δ = 0.01 × 50 000 = 500 € + downstream.
  - `_M100_BASE_INPUTS_AND_STABLE_COMPUTED` shared input dict
    (year-stable values).
- Added `_modelo_100_art20_piece_a_fixture` and
  `_modelo_100_art20_piece_b_fixture` — path-override fixtures for
  the LIRPF art. 20 piecewise reducción in casilla 0021 (the two
  pieces share a `max_op` so only the active piece is observable).
- Added `_SUB_OP_PATH_OVERRIDES` table mapping
  `(ruleset_id, casilla, path) → fixture` for the 12 piece_a +
  piece_b path entries (4 paths × 3 years).
- Extended `_SUB_OP_COVERAGE_DATA` with 22 M100 casilla entries
  per year × 3 years = 66 entries; the walker yields all 71
  `SubFormula` descendants per year, total 213 sub_op coverage
  entries.

`test_scalar_mutation.py`:

- Replaced the 9-archetype selective enumeration with a
  comprehensive 60-entry table: 20 leaves per year × 3 years.
- Added `_M100_LEAF_PATHS` constant declaring every
  `iter_scalar_leaf_paths`-yielded path (verified by
  `test_m100_selective_paths_match_walker`).
- Added `_f100_art20_piece_b_slope_for_scalar()` for the 1.14
  slope leaf (rendimiento 18 500 € so piece_b wins).
- Re-uses `_modelo_100_full_fixture_2024` /
  `_modelo_100_full_fixture_post_2025` from the operand-swap module
  for 0225 / 0540 / 0542 / 0560 leaves.

## Wave 3 — non-M100 deferred coverage (subsumed)

The Wave 1 path-based generalisation automatically covers:

- Inner sub_ops in M130 casilla 07 + 17 (both nested
  `sub_op(sub_op(...), ref)`).
- Inner sub_ops in M131 casilla 10 + 13.
- Inner sub_ops in M200 casilla 00611 (4-deep nest) + 00621.
- Inner sub_ops in M202 casilla 32 (3-deep nest).

Wave 2's `_SUB_OP_COVERAGE_DATA` extension picks up:

- M111 2024 + M115 2024 + M131 2024 (previously not imported).
- M390 casilla 193 (`clamp_pos(sub_op(0, 191))`) — newly mutable
  via the path-based helper.
- M100 summary 0698 outer + 0720 inner (previously outer-only).
- M200 casilla 00621 (1 sub_op, previously not parametrised).

## Wave 4 — audit

- `EXPECTED_COUNTS` deferred totals: all `*_deferred` columns =
  `0`. The `test_deferred_count_matches_empirical_coverage_gap`
  invariant verifies this matches the per-class harness empirical
  coverage exactly.
- `test_catalogue_totals_are_non_trivial` updated: previously
  asserted the deferred totals were *non-zero* (issue #457 starting
  state); now asserts they are *zero* (Wave 2 closure state).
- `just lint && just typecheck && just hooks && just test` all
  green. `just test-cov` reports 80.52 % coverage on `src/aeat`
  (≥ 60 % floor).

## Catalogue (post-Wave-2)

| Ruleset                  | sub_op | sub_op_deferred | percent_rate | brackets_threshold | mul_div_scalar | mul_div_scalar_deferred | unflagged |
| :----------------------- | ----: | --------------: | -----------: | -----------------: | -------------: | ----------------------: | --------: |
| `modelo_100.{2024..26}`  |    71 |               0 |            0 |                  0 |             20 |                       0 |         0 |
| `modelo_100.summary.2025`|     3 |               0 |            0 |                  0 |              0 |                       0 |         0 |
| All other rulesets       |  ...  |               0 |          ... |                ... |            ... |                       0 |       ... |
| **TOTAL**                |   297 |           **0** |           33 |                  4 |             67 |                   **0** |         7 |

Pre-#457: every `_deferred` column would have been 0 (no column
existed); empirical kill-rate was inflated by the
`killed = populated` tautology. Post-#457 + Wave 2: every column is
honest and zero-deferred.

## Total tests on the mutation harness suite

| Module                                           | Pre-#457 | Post-Wave-2 |
| :----------------------------------------------- | -------: | ----------: |
| `test_brackets_threshold_mutation.py`            |       10 |          10 |
| `test_mutator_exhaustiveness.py`                 |        5 |           5 |
| `test_mutator_kill_rate.py`                      |       35 |          38 |
| `test_mutator_tautology_regression.py`           |        0 |           4 |
| `test_operand_swap_mutation.py`                  |       50 |         310 |
| `test_percent_rate_mutation.py`                  |       71 |          71 |
| `test_scalar_mutation.py`                        |       17 |         132 |
| **TOTAL**                                        |  **188** |     **570** |

## Follow-up issues to close at PR-update time

- **#460** (M100 mul/div scalar coverage gap) — closed by Wave 2.
  Comment with link to this exec summary.
- **#461** (M100 sub_op coverage gap) — closed by Wave 1+2.
  Comment with link.

(The follow-up issues filed at initial PR-open time are now
satisfied by the Wave 2 closure; left open for one cycle to allow
reviewer comment, then closed.)
