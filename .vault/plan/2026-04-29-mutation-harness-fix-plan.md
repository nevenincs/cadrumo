---
tags:
  - '#plan'
  - '#mutation-harness-fix'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-mutation-harness-fix-adr]]'
  - '[[2026-04-29-mutation-harness-fix-research]]'
---

# Plan — `mutation-harness-fix`

Implementation plan for issue #457 / branch
`chore/457-mutation-harness-fix`. Implements ADR
`2026-04-29-mutation-harness-fix-adr`.

## Phase 1 — Harness mechanics (helper generalisation)

### Step 1.1 — Generalise `_mutate_outer_sub_op` to descend through `ClampPositiveFormula`

File: `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py`.

- Add a private `_find_outer_sub_op(node)` helper that walks down
  through `RoundFormula` and `ClampPositiveFormula` wrappers and
  returns the path-prefix to the first `SubFormula`. Raise
  `TypeError` if no `SubFormula` is reachable through the wrapper
  chain.
- Refactor `_mutate_outer_sub_op` to use `_find_outer_sub_op` —
  preserving its existing behaviour for direct
  `RoundFormula(SubFormula(...))` bodies.
- Add a regression test
  `test_mutate_outer_sub_op_descends_through_clamp_pos` that swaps
  a clamp-wrapped sub_op (e.g. M390 casilla 193 used as a
  representative case — fixture provides 191=10 800 so swap of the
  `sub_op(0, 191)` produces a non-zero discrepancy on 193).

## Phase 2 — Aggregator refactor

### Step 2.1 — Expose per-class harness coverage generators

File: `src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py`.

- Rename the local `_build_test_params()` to expose two generators:
  - `_build_test_params()` — keeps yielding the parametrize cases
    (preserves the existing test).
  - `_iter_scalar_targets()` — yields `(ruleset_id, casilla_id,
    leaf_path)` triples (the unique mutation-target signatures).
  - `_build_test_params()` is rewritten to consume
    `_iter_scalar_targets()` and fan out into +1 % / -1 %
    directions. This is a refactor that preserves behaviour.

File: `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py`.

- Add `_iter_percent_targets()` yielding `(ruleset_id, casilla_id,
  signature)` where signature is `f"literal:{path}"` or
  `f"param:{param_id}"`.

(`test_brackets_threshold_mutation.py` covers a single synthetic
ruleset with 4 brackets — the count is a constant; no generator
needed.)

### Step 2.2 — Refactor the aggregator

File: `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`.

- Import `_iter_scalar_targets` from `.test_scalar_mutation` and
  `_iter_percent_targets` from `.test_percent_rate_mutation`.
- Compute `empirical_coverage` per `(ruleset_id, mutator_class)`
  by counting unique target signatures from the imported generators.
- Replace `killed = populated` in
  `test_aggregate_kill_rate_floor_is_satisfied` with `killed =
  sum(empirical_coverage[r][c] for ... in scope)`.
- Subtract `*_deferred` counts from the populated denominator before
  the kill-rate division.
- Add new test `test_deferred_count_matches_empirical_coverage_gap`
  that asserts per ruleset and per mutator class:
  `populated - empirical_coverage == declared_deferred`.

### Step 2.3 — Update `EXPECTED_COUNTS`

For every M100 row (`modelo_100.2024 / 2025 / 2026`):

```python
"mul_div_scalar_deferred": 17,    # 20 populated - 3 covered (3 archetypes)
"sub_op_deferred": 65,             # 71 populated - 6 covered (0545 + 0720)
```

For every other ruleset row, add `"mul_div_scalar_deferred": 0` and
`"sub_op_deferred": 0` columns (deferred = 0 when fully covered or
when populated = 0).

For the synthetic-brackets ruleset (added in the catalogue not in
`ALL_RULESETS`), no deferred columns are needed (single ruleset,
fully covered).

### Step 2.4 — Catalogue markdown surfaces deferred columns

`build_catalogue_markdown()` gains two new columns:

| ... | mul_div_scalar | mul_div_scalar_deferred | sub_op_deferred | unflagged |

`test_catalogue_markdown_includes_every_landed_ruleset` and
`test_catalogue_totals_are_non_trivial` updated to reflect the new
columns.

## Phase 3 — M100 fixture additions

### Step 3.1 — M100 mul/div scalar fixtures

File: `src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py`.

- Import `MODELO_100_2024 / 2025 / 2026` from the package.
- Add three fixture functions per year:
  - `_f100_2024_tarifa_general_fixture()` — drives BLG into the
    22.5 % bracket of TARIFA_ESTATAL_GENERAL_2024 (60 000–300 000).
    Set 0545 base liquidable to 100 000 € (input) so the 22.5 %
    bracket portion is 40 000 € and a ±1 % rate shift moves
    casilla 0540 by ~400 €.
  - `_f100_2024_tarifa_ahorro_fixture()` — drives BLA into the top
    bracket of TARIFA_ESTATAL_AHORRO_2024 (>300 000 € at 14 %).
    Same delta-detection logic.
  - `_f100_2024_art20_slope_fixture()` — drives 0020
    (rendimiento neto previo) to 16 000 € so piece_a is active
    (slope 1.75); a ±1 % shift moves the reducción at 0021 by a
    detectable amount.
- Same pattern for 2025 and 2026 (TARIFA_ESTATAL_AHORRO top bracket
  rate is 0.15 in 2025/2026 vs 0.14 in 2024 — the fixture drives
  values that produce a detectable delta on either rate).
- Extend the parametrize list with selective `(ruleset, casilla,
  leaf_path, fixture)` entries for the 3 archetypes per year.
  Selective parametrization (rather than `iter_scalar_leaf_paths`
  walking) is important because not every leaf has a viable
  fixture in this PR — see ADR D5.
- The existing `_build_test_params()` for non-M100 rulesets stays
  unchanged.

### Step 3.2 — M100 sub_op fixtures

File: `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py`.

- Import `MODELO_100_2024 / 2025 / 2026`.
- Add `_modelo_100_full_fixture()` — single fixture covering both
  0720 and 0545 chains (asymmetric values: 0432=80 000, 0445=20 000,
  0455=10 000, 0698=50 000, 0699=8 000, 0700=2 000; computed values
  0545=50 000 baseline, 0720=40 000 baseline). The same fixture
  drives 6 parametrize cases (2 casillas × 3 years).
- Add 6 `pytest.param` entries to the existing parametrize block,
  one per (year, casilla).
- The fixture intentionally provides extra context (full-form M100
  is large; the fixture provides only what 0432/0445/0455/0698/0699/0700
  + their direct dependencies need to drive the chains, with all
  other casillas defaulting to 0).

### Step 3.3 — Verify selective parametrization stays in sync with EXPECTED_COUNTS

Quick sanity-check test:
`test_m100_scalar_archetype_count_matches_deferred` asserts that
each M100 row's `mul_div_scalar_deferred` equals `mul_div_scalar - 3`
(the 3 archetypes added). Same for `sub_op_deferred = sub_op - 2`.

## Phase 4 — Tautology regression defense

### Step 4.1 — `test_mutator_tautology_regression.py`

File: `src/aeat/domain/formulas/_rulesets/test_mutator_tautology_regression.py` (NEW).

The regression test cluster:

1. `test_aggregator_catches_uncovered_populated_node` — constructs
   a synthetic copy of `EXPECTED_COUNTS` with one row's
   `mul_div_scalar` bumped by +1 and `mul_div_scalar_deferred`
   left unchanged. Calls the aggregator's
   `compute_kill_rate_components` (a small refactor extraction
   from `test_aggregate_kill_rate_floor_is_satisfied`) and asserts
   it returns a populated count that exceeds the empirical
   coverage by 1.

2. `test_deferred_growth_without_followup_fails_loudly` —
   constructs a synthetic `EXPECTED_COUNTS` row where the deferred
   number is bumped without a corresponding decrease in empirical
   coverage. Asserts the new
   `test_deferred_count_matches_empirical_coverage_gap` invariant
   fails.

3. `test_old_killed_equals_populated_pattern_is_unreachable` —
   meta-test asserting that the aggregator no longer contains the
   literal expression `killed = populated` outside the regression
   test (a code-spelling guard). Implemented by reading
   `test_mutator_kill_rate.py` source and grepping for the offending
   pattern. Belt-and-braces.

Module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`.

## Phase 5 — Vault execution records + summary

### Step 5.1 — Per-step exec records

Files under
`.vault/exec/2026-04-29-mutation-harness-fix/2026-04-29-mutation-harness-fix-phase1-task1.md`,
…, one per Phase × Step (Phase 1 / Phase 2 / Phase 3 / Phase 4).

### Step 5.2 — Phase summary

`.vault/exec/2026-04-29-mutation-harness-fix/2026-04-29-mutation-harness-fix-phase1-summary.md`

Captures:

- Per-modelo before/after kill-rate (mul/div scalar) — the table
  from the ADR's "Per-modelo before/after kill-rate" section,
  with the `After empirical (post-fix)` column populated by actual
  `pytest --collect-only` counts.
- Per-modelo before/after sub_op coverage table.
- The full output of `git log origin/main..HEAD --oneline`
  AFTER the rebase-out-#216 step, proving the PR diff is clean.
- Links to the follow-up issues filed.

## Phase 6 — Mandatory code review

### Step 6.1 — Run `vaultspec-code-review` skill

Cover the seven safety invariants from the handover prompt's STEP 2:

1. Tautology fixed.
2. Aggregator accuracy (verified by Phase 4 regression tests).
3. No regression on existing modelos (per-modelo before/after
   table shows no degradation).
4. Orphan-node defense intact (`test_mutator_exhaustiveness.py`
   passes — no changes to MUTATOR_REGISTRY or NOT_MUTABLE_NODE_TYPES).
5. NO MOCKS introduced.
6. #216 cleanly rebased out (Step 7.1 below).
7. Test markers preserved at module level.

Plus the standard project mandates: PYDANTIC v2 strict for any new
model (none introduced in this PR; all changes are test
infrastructure), typed signatures, Google-style docstrings, errors
inherit from `aeat.core.errors.AeatError`, logging via
`aeat.core.logging.get_logger(__name__)` only, public API discipline,
NO wave/phase numbering in source code or docstrings, lint /
typecheck / test / hooks all green.

## Phase 7 — Rebase out #216 + open PR

### Step 7.1 — Cherry-pick #457 commits onto a fresh branch

```bash
# Identify own commits (everything past the merge commit 76ff882):
git log --oneline 76ff882..HEAD > /tmp/my-commits.txt

# Reverse the order so cherry-pick applies them oldest-first:
tac /tmp/my-commits.txt > /tmp/my-commits-fwd.txt

# Cherry-pick onto a fresh branch from origin/main:
git fetch origin
git checkout -b chore/457-mutation-harness-fix-clean origin/main
xargs -a /tmp/my-commits-fwd.txt -I{} git cherry-pick {}

# Verify clean diff:
git log origin/main..HEAD --oneline
# MUST show ONLY #457 commits.

# Force-update the original branch:
git checkout chore/457-mutation-harness-fix
git reset --hard chore/457-mutation-harness-fix-clean
git push --force-with-lease origin chore/457-mutation-harness-fix
```

### Step 7.2 — Open PR with rebase-out evidence

PR title: `fix(formulas/rulesets): mutation harness kill-rate tautology + fixture redesign (#457)`.

PR body (HEREDOC-style):

```
## Summary

Closes #457. Replaces the `killed = populated` tautology in
`test_aggregate_kill_rate_floor_is_satisfied` with empirical
coverage computed from the per-class harness parameter tables.
Adds M100 mul/div scalar fixtures (3 archetypes × 3 years) and
M100 sub_op fixtures (2 archetypes × 3 years) per the issue's
prescribed scope. Adds a tautology regression-defense module
(`test_mutator_tautology_regression.py`) that catches future PRs
that bump populated counts without extending the per-class
harness or the deferred catalogue.

## Per-modelo before/after kill-rate

(table from exec summary)

## Per-modelo before/after sub_op coverage

(table from exec summary)

## Follow-up issues filed

- #NEW-A — M100 mul/div scalar coverage gap (51 leaves still
  deferred per year)
- #NEW-B — M100 sub_op coverage gap (65 chains still deferred per
  year)
- #NEW-C — M390 casilla 193 sub_op coverage (clamp-wrapped chain
  newly mutable post-`_mutate_outer_sub_op` generalisation)

## Rebase-out evidence

(output of `git log origin/main..HEAD --oneline` AFTER rebase-out)

## Refs

- ADR ``2026-04-29-mutation-harness-fix-adr``
- Research `[[2026-04-29-mutation-harness-fix-research]]`
- Plan `[[2026-04-29-mutation-harness-fix-plan]]`
- Parent EPIC #455 (M100 deferred extensions umbrella)
- Sibling: #338 (mutation harness extension)
```

## Risk register

| Risk                                                                        | Likelihood | Impact | Mitigation                                                                                                                  |
| :-------------------------------------------------------------------------- | :--------: | :----: | :-------------------------------------------------------------------------------------------------------------------------- |
| Aggregator import of per-class generators creates circular import           |    low     | medium | Generators are imported inside the test function, not at module load time.                                                  |
| `_mutate_outer_sub_op` generalisation breaks an existing test case          |    low     | high   | Add the descent-through-clamp_pos test BEFORE refactoring; existing tests verify behaviour preserved on direct sub_op cases. |
| M100 fixture drives a baseline that fails clean-audit                       |   medium   | medium | Each fixture validated with `engine.audit_against` before mutation; fixture computed values match engine derivations.       |
| Selective parametrization fails the `iter_scalar_leaf_paths` walker        |    low     | medium | The walker is unchanged; selective parametrization is a separate code path that does NOT replace the existing walker logic. |
| Cherry-pick during rebase-out introduces conflicts with origin/main         |   medium   | medium | Each #457 commit is small, harness-only, and touches files unmodified by recent main commits.                              |
| Force-push damages other agents' work on the branch                         |    low     | high   | `--force-with-lease` rejects the push if the remote has been updated since the last fetch. No other agent is on this branch.|

## Acceptance gate

This plan is approved (self-approval per apex-PM mandate) when
every step has a corresponding exec record under
`.vault/exec/2026-04-29-mutation-harness-fix/` AND the Phase 6
code-review covers the seven safety invariants AND `git log
origin/main..HEAD --oneline` shows only #457 commits AND the PR
is opened against `main`.
