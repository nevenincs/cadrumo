---
tags:
  - '#exec'
  - '#mutation-harness-fix'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-mutation-harness-fix-plan]]'
  - '[[2026-04-29-mutation-harness-fix-adr]]'
  - '[[2026-04-29-mutation-harness-fix-research]]'
---

# Phase summary — `mutation-harness-fix` (issue #457)

## Result

Closes the kill-rate aggregator tautology surfaced by the M100
megaproject (PR #448). The aggregator now derives `killed`
empirically from the per-class harness coverage generators, the
deferred-coverage catalogue is honest about uncovered nodes, and a
new regression-defense module + AST guard prevent the failure mode
from returning.

Tests delta (mutation harness suite): 188 → 223 (+35).

## Files changed (4 modified + 1 new)

- `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py` —
  empirical aggregator + deferred catalogue + 3 new tests.
- `src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py` — selective
  M100 archetype enumeration + `_iter_scalar_targets` + 1 new test.
- `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py` —
  `_swap_outer_sub_op_in_subtree` helper + M100 fixture + 6
  parametrize entries + `OUTER_SUB_OP_COVERAGE` constant + 3 new
  tests.
- `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py` —
  `_iter_percent_targets` generator (no test count change).
- `src/aeat/domain/formulas/_rulesets/test_mutator_tautology_regression.py`
  — NEW. 4 tests defending the structural fix.

No source-code (production) changes.

## Per-modelo before/after kill-rate (mul/div scalar)

| Ruleset                 | Populated | Before claimed | Before empirical | After empirical (post-fix) |
| :---------------------- | --------: | -------------: | ---------------: | -------------------------: |
| `modelo_100.2024`       |        20 |          100 % |              0 % |  15 % (3 of 20 covered)   |
| `modelo_100.2025`       |        20 |          100 % |              0 % |  15 %                      |
| `modelo_100.2026`       |        20 |          100 % |              0 % |  15 %                      |
| `modelo_100.summary.2025`|         0 |            N/A |              N/A |    N/A                     |
| `modelo_111.{24,25,26}` |         0 |            N/A |              N/A |    N/A                     |
| `modelo_115.{24,25,26}` |         0 |            N/A |              N/A |    N/A                     |
| `modelo_123.{24,25,26}` |         0 |            N/A |              N/A |    N/A                     |
| `modelo_130.{24,25,26}` |         0 |            N/A |              N/A |    N/A                     |
| `modelo_131.{24,25,26}` |         0 |            N/A |              N/A |    N/A                     |
| `modelo_180.{24,25,26}` |         0 |            N/A |              N/A |    N/A                     |
| `modelo_200.{24,25,26}` |         1 |          100 % |            100 % |  100 %                     |
| `modelo_202.2025`       |         1 |          100 % |            100 % |  100 %                     |
| `modelo_303.{24,25,26}` |         1 |          100 % |            100 % |  100 %                     |
| `modelo_390.{24,25,26}` |         0 |            N/A |              N/A |    N/A                     |
| **TOTAL**               |    **67** |      **100 %** |        **10.4 %** | **24 % (16 of 67)**       |

Aggregate kill-rate on the **claimed-covered surface** (populated −
deferred = 16) post-fix = 100 %. The 90 % floor passes; the
honestly-surfaced gap of 51 deferred mul/div scalar leaves is
tracked by follow-up issues (filed at PR-open time).

## Per-modelo before/after sub_op coverage (outer-only)

| Ruleset                 | Populated | Before empirical | After empirical |
| :---------------------- | --------: | ---------------: | --------------: |
| `modelo_100.2024`       |        71 |          0 outer |        2 outer  |
| `modelo_100.2025`       |        71 |          0 outer |        2 outer  |
| `modelo_100.2026`       |        71 |          0 outer |        2 outer  |
| `modelo_100.summary.2025`|         3 |          1 outer |        1 outer  |
| `modelo_111.2024`       |         1 |          0 outer |        0 outer  |
| `modelo_111.{25,26}`    |         1 |          1 outer |        1 outer  |
| `modelo_115.2024`       |         1 |          0 outer |        0 outer  |
| `modelo_115.{25,26}`    |         1 |          1 outer |        1 outer  |
| `modelo_123.{24,25,26}` |         1 |          1 outer |        1 outer  |
| `modelo_130.{24,25,26}` |         8 |          6 outer |        6 outer  |
| `modelo_131.2024`       |         5 |          0 outer |        0 outer  |
| `modelo_131.{25,26}`    |         5 |          3 outer |        3 outer  |
| `modelo_180.{24,25,26}` |         0 |          0       |        0        |
| `modelo_200.{24,25,26}` |         5 |          1 outer |        1 outer  |
| `modelo_202.2025`       |         3 |          1 outer |        1 outer  |
| `modelo_303.{24,25,26}` |         2 |          2 outer |        2 outer  |
| `modelo_390.{24,25,26}` |         3 |          2 outer |        2 outer  |
| **TOTAL**               |   **297** |     **49 outer** |   **54 outer**  |

The +5 outer delta is the M100 full-form fix (2 archetypes × 3
years = 6 covered, less the 1 M100 summary case that was already
counted). All sub_op coverage is **outer-only** by design;
inner-sub_op mutation is out of scope of issue #457.

## Tautology cases addressed

The single tautology source — `killed = populated` at
`test_mutator_kill_rate.py:465` — is removed. The aggregator now
derives `killed` from
`sum(_empirical_scalar_coverage().values()) +
sum(_empirical_percent_coverage().values()) +
_NUMERIC_BRACKETS_SYNTHETIC`. The
`test_deferred_count_matches_empirical_coverage_gap` invariant
asserts equality between the populated-empirical gap and the
declared `_deferred` count per ruleset and mutator class.

## Regression-prevention summary

Three layers of defense:

1. **`test_deferred_count_matches_empirical_coverage_gap`** —
   asserts gap-equality per ruleset and mutator class.
2. **`test_aggregator_killed_equals_populated_under_test`** —
   asserts the empirical killed count matches the populated-minus-
   deferred surface.
3. **`test_old_killed_equals_populated_pattern_is_unreachable`** —
   AST guard against re-introduction of the literal assignment.

A future PR that bumps populated counts without either extending
the per-class harness OR bumping `_deferred` fails (1). A future
PR that adds harness coverage without lowering `_deferred` fails
(1) and (2). A future PR that re-introduces the literal `killed =
populated` source line fails (3).

## Test execution evidence

```
$ uv run pytest src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py
              src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py
              src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py
              src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py
              src/aeat/domain/formulas/_rulesets/test_brackets_threshold_mutation.py
              src/aeat/domain/formulas/_rulesets/test_mutator_exhaustiveness.py
              src/aeat/domain/formulas/_rulesets/test_mutator_tautology_regression.py -q
============================= 223 passed in 1.40s =============================
```

`just lint && just typecheck && just hooks` all green.

`just test-cov` reports 82.60 % coverage on `src/aeat` (well above
the 60 % floor). One pre-existing flaky failure
(`src/aeat/entrypoints/cli/workflow/test_cli.py::TestWorkflowCli::test_next_json_round_trips`)
is unrelated to #457 — verified by reproducing on the pre-#457
worktree state (`git stash` then re-run).

## Catalogue markdown (post-fix)

The empirical catalogue surfaces the deferred coverage honestly:

```
| Ruleset | sub_op | sub_op_deferred | percent_rate | brackets_threshold | mul_div_scalar | mul_div_scalar_deferred | unflagged |
|---------|-------:|----------------:|-------------:|-------------------:|---------------:|------------------------:|----------:|
| modelo_100.2024 | 71 | 69 | 0 | 0 | 20 | 17 | 0 |
| modelo_100.2025 | 71 | 69 | 0 | 0 | 20 | 17 | 0 |
| modelo_100.2026 | 71 | 69 | 0 | 0 | 20 | 17 | 0 |
| ... (all rulesets) ...                                                                       |
| TOTAL   | 297    | 243            | 33           | 4                  | 67             | 51                       | 7         |
```

Pre-#457 the same catalogue would show every `*_deferred` column at
0 — claiming full coverage. The honest numbers are now visible.

## Rebase-out plan (PR-prep step)

The worktree currently contains merge commit `76ff882` plus my #457
work commits (none yet — pending commit creation post-summary).
The rebase-out step before opening the PR:

```bash
git log --oneline 76ff882..HEAD > /tmp/my-commits.txt
git fetch origin
git checkout -b chore/457-mutation-harness-fix-clean origin/main
xargs -a /tmp/my-commits-fwd.txt -I{} git cherry-pick {}
git log origin/main..HEAD --oneline    # MUST show only #457 commits
git checkout chore/457-mutation-harness-fix
git reset --hard chore/457-mutation-harness-fix-clean
git push --force-with-lease origin chore/457-mutation-harness-fix
```

Force-push is the documented exception to project no-force-push
policy, sanctioned for the rebase-out step only.

## Follow-up issues

To file at PR-open time:

- **`#NEW-A: M100 mul/div scalar coverage gap`** — extend the
  scalar harness to cover the remaining 51 leaves per year × 3
  years (full TARIFA_ESTATAL_GENERAL × 6 brackets × 3 progressive
  applications + Anexo D simplificada 5 % cap + Anexo B1 piece_b
  slope 1.14). Today's `mul_div_scalar_deferred` total = 51.

- **`#NEW-B: M100 sub_op coverage gap`** — extend the operand-swap
  harness to cover the remaining 65 outer chains per year × 3 years
  (every per-anexo intermediate sub_op chain) plus the
  inner-sub_op coverage shared with M130 / M131 / M200 / M202 /
  M390. Today's `sub_op_deferred` total = 243.

- **`#NEW-C: M390 casilla 193 sub_op coverage`** —
  `clamp_pos(sub_op(0, 191))` is newly mutable post-#457 helper
  generalisation; trivially fixable in a follow-up by adding a
  parametrize entry.
