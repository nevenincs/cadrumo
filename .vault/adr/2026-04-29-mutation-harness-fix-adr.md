---
tags:
  - '#adr'
  - '#mutation-harness-fix'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-mutation-harness-fix-research]]'
  - '[[2026-04-25-mutation-harness-extension-adr]]'
  - '[[2026-04-25-mutation-harness-extension-research]]'
---

# ADR — `mutation-harness-fix`: empirical kill-rate aggregator + M100 fixture coverage

## Status

Approved (self-approval per the apex-PM mandate; no human-in-the-loop).

## Context

`test_mutator_kill_rate.py::test_aggregate_kill_rate_floor_is_satisfied`
hard-codes `killed = populated`, so the kill-rate floor is
**structurally vacuous** for nodes that live in `EXPECTED_COUNTS` but
are not enumerated by any per-class harness. The PR #448 M100
megaproject exposed the gap: 60 mul/div scalar leaves and 213 `sub_op`
nodes were added to `EXPECTED_COUNTS` without extending the per-class
harnesses to import the M100 rulesets. The aggregate kill-rate
continues to report 100 %; empirical mul/div scalar kill-rate is 10.4 %
(7 of 67 nodes mutated). See
`2026-04-29-mutation-harness-fix-research` for the full audit.

The fix must:

- replace the tautology with an **empirical** kill-rate computation
  driven by the per-class harnesses' actual parameter tables;
- preserve the 90 % floor on the **claimed-covered** surface;
- defend the regression so a future ruleset addition cannot silently
  re-introduce the same gap;
- close the immediately-fixable subset of the M100 mutation gap (≥ 1
  fixture per year for the prescribed scalar / sub_op archetypes),
  and file follow-up issues for the remaining coverage work.

The fix must NOT:

- modify per-modelo rulesets or formulas — the change is harness-only;
- introduce new mutator classes (that is #338's territory);
- couple to `aeat.adapters.persistence.storage` / `aeat.domain.financial` (#216 territory; the
  pre-merged WIP is for visibility only and is rebased out before the
  PR opens);
- introduce mocks, fakes, or stubs (project mandate).

## Decision

### D1 — `killed` becomes empirical, computed from per-class harnesses

`test_aggregate_kill_rate_floor_is_satisfied` will:

1. Import each per-class harness's parameter generator
   (`test_scalar_mutation._build_scalar_targets()`,
   `test_percent_rate_mutation._build_percent_targets()`, and the
   parametrize literal block of `test_operand_swap_mutation` does not
   feed kill-rate today and stays out of scope here).
2. Count **unique** `(ruleset_id, casilla_id, target_signature)`
   triples — `target_signature` is the leaf-path tuple for scalar,
   `f"literal:{path}"` or `f"param:{param_id}"` for percent, and
   `f"bracket:{bracket_index}"` for the brackets harness.
3. Sum the counts per mutator class to derive `killed_per_class`.
4. Compute `populated_under_test = sum(killed_per_class)` (the per-
   class harness fail-fast contract guarantees `killed == populated_under_test`
   at floor-check time).

The per-class generators must be public-name-stable (`_build_*`
prefix) so the aggregator can import them deterministically.

### D2 — `EXPECTED_COUNTS` gains a `_deferred` column per mutator class

For mutator classes whose populated surface includes nodes whose
per-class harness coverage has been deliberately deferred to a
follow-up issue, a new column documents the gap:

```python
EXPECTED_COUNTS["modelo_100.2024"] = {
    "sub_op": 71,
    "sub_op_deferred": 65,                       # 71 populated - 6 covered (0545 + 0720)
    "percent_rate_literal": 0,
    "percent_rate_param": 0,
    "percent_rate_compound_skipped": 0,          # delegated to mul/div scalar
    "percent_rate_casilla_ref_skipped": 0,       # out-of-AST input
    "brackets_threshold_non_terminal": 0,
    "mul_div_scalar": 20,
    "mul_div_scalar_deferred": 17,               # 20 populated - 3 covered (3 archetypes)
}
```

The aggregator subtracts `<class>_deferred` from the populated count
when computing the kill-rate floor. Deferred nodes still appear in
the catalogue markdown under a new "deferred" column so they are
visible to readers.

`sub_op_deferred` is added even though `sub_op` is not in the
kill-rate floor today — the column exists so the catalogue accurately
reflects the gap and so a future bracket-floor extension to `sub_op`
inherits the same machinery.

### D3 — A new test asserts `populated_total - populated_under_test == sum_of_deferred`

This is the regression defense. If a future PR bumps a populated
count without either extending the per-class harness OR bumping the
matching `_deferred` count, the assertion fails:

```python
def test_deferred_count_matches_empirical_coverage_gap() -> None:
    for ruleset_id, counts in EXPECTED_COUNTS.items():
        gap_scalar = counts["mul_div_scalar"] - empirical_scalar_coverage[ruleset_id]
        assert gap_scalar == counts.get("mul_div_scalar_deferred", 0), (
            f"{ruleset_id}: mul_div_scalar gap {gap_scalar} does not match "
            f"declared deferred count {counts.get('mul_div_scalar_deferred', 0)}. "
            f"Either extend the per-class harness or update the deferred catalogue."
        )
        # … same for sub_op, percent_rate, brackets_threshold.
```

This is the **tautology regression test** — it catches the precise
failure mode that motivates this ADR.

### D4 — `_mutate_outer_sub_op` descends through `ClampPositiveFormula`

The helper in `test_operand_swap_mutation.py` is generalised to find
the outermost `SubFormula` regardless of whether the formula body is
`RoundFormula(SubFormula(…))` or `RoundFormula(ClampPositiveFormula(SubFormula(…)))`.
The implementation walks down through any `RoundFormula` /
`ClampPositiveFormula` wrappers and raises `TypeError` only if the
first non-wrapper node is not a `SubFormula`. This unblocks fixtures
for M100 0545 (and the analogous M100 0550 / 0698, M390 193).

### D5 — M100 mul/div scalar fixtures: 3 archetypes × 3 years

Per the issue scope:

- **TARIFA_ESTATAL_GENERAL bracket rate**: the 22.5 % rate on the
  60 000–300 000 € bracket of casilla 0540 (cuota tarifa estatal
  general on BLG). Same node exists in casilla 0542 (mínimo) but
  the harness mutates one node per ruleset — the BLG application is
  the canonical Kent-relevant one.
- **TARIFA_ESTATAL_AHORRO bracket rate**: the top-bracket rate on
  casilla 0560 (cuota integra estatal del ahorro). The 14 %→15 %
  Ley 7/2024 delta means 2024 has rate 0.14 and 2025/2026 have rate
  0.15 — the harness mutates whichever rate is correct per year.
- **LIRPF art. 20 slope**: the 1.75 slope literal in piece_a of
  Anexo B1's reducción art. 20 (or the 1.14 slope in piece_b — the
  fixture exercises piece_a as the more common case).

Each archetype is added as a parametrized case keyed by
`(ruleset, casilla_id, leaf_path)` rather than walking
`iter_scalar_leaf_paths` over the M100 ruleset (which would
parametrise all 20 leaves per year and require fixtures hitting
each — out of scope). The selective parametrization is a deliberate
pattern: the per-modelo M100 fixture covers the 3 archetypes the
issue calls out, and the rest go to `mul_div_scalar_deferred` for
follow-up.

### D6 — M100 sub_op fixtures: 2 archetypes × 3 years

Per the issue scope:

- **Casilla 0720** (cuota diferencial = autoliquidación result):
  `sub_op(sub_op(ref("0698"), ref("0699")), ref("0700"))`. Body is
  Round-wrapped; outer swap flips `cuota_diferencial` sign.
- **Casilla 0545** (base liquidable general):
  `clamp_pos(sub_op(sub_op(ref("0432"), ref("0445")), ref("0455")))`.
  Body is Round → ClampPos → Sub. Outer swap requires D4
  generalisation; the swap converts `clamp_pos(BIG - reducciones)` to
  `clamp_pos(reducciones - BIG)`, surfacing as a discrepancy on 0545
  with sign-flip magnitude.

Each year (2024/2025/2026) gets one fixture per casilla. The
fixture intentionally drives non-zero asymmetric values into the
sub_op operands so the swap produces a delta ≥ 0.02 € on the
target casilla.

### D7 — Public API discipline + test markers

- New M100 scalar / sub_op fixtures live in the existing
  `test_scalar_mutation.py` / `test_operand_swap_mutation.py` modules
  (no new test module for the fixtures). The new tautology
  regression test is a **separate** module
  `test_mutator_tautology_regression.py`.
- Module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`.
- All tests use real `Ruleset` instances + real `Engine` calls; no
  mocks. The mutators in `_mutators.py` are unchanged in this PR
  except for the helper generalisation (D4) is folded into
  `test_operand_swap_mutation.py` as a private function (consistent
  with the existing `_mutate_outer_sub_op` location).

### D8 — Rebase out the pre-merged #216 WIP before the PR opens

The worktree currently contains a merge commit (`76ff882`) that pre-
pulls ~97 commits of `feature/216-bank-import-persistence` for
visibility. Per the handover prompt's PR-prep mandate, the PR diff
must contain **only** #457 commits. The rebase-out step:

```bash
git checkout -b chore/457-mutation-harness-fix-clean origin/main
git cherry-pick <#457-sha-1> <#457-sha-2> …          # one cherry-pick per #457 commit
git log origin/main..HEAD --oneline                  # verify ONLY #457 commits visible
git checkout chore/457-mutation-harness-fix
git reset --hard chore/457-mutation-harness-fix-clean
git push --force-with-lease origin chore/457-mutation-harness-fix
```

The force-push is the **only** sanctioned force-push in this PR
(documented exception to project policy). The exec summary records
the actual `git log` output for audit.

## Consequences

### Positive

- The aggregate kill-rate test reflects the **true** mutation-detection
  signal. Future ruleset PRs cannot silently inflate it.
- The deferred-coverage catalogue is **honest** — readers see the
  gap and can prioritise follow-up work. Today the catalogue claims
  full coverage, masking the gap.
- The `_mutate_outer_sub_op` generalisation enables sub_op fixtures
  for clamp-wrapped chains (M100 0545, M100 0550, M100 0698, M390
  193), so the harness can grow naturally as Tier-L modelos add
  clamp-wrapped sub_op chains.
- The tautology regression test (`test_deferred_count_matches_empirical_coverage_gap`)
  surfaces a structural class of bug — not a one-shot fix.

### Negative

- The aggregator's coverage computation cross-imports per-class
  harness internals (`_build_*` generators). This couples the
  aggregator to the per-class test modules. Mitigation: the
  generators are private (`_`-prefixed) and named by convention; a
  `test_mutator_kill_rate` test asserts each per-class module
  exposes the expected generator name.
- `EXPECTED_COUNTS` rows grow by up to 4 columns (`*_deferred`).
  Each row's deferred count must be kept in sync with the
  per-class harness coverage — the regression test asserts this,
  but it adds reviewer burden.
- The kill-rate computation is now derived from the per-class
  param tables rather than a fixed table; any per-class harness
  refactor that changes the empirical count must update the
  deferred numbers in the same PR.

### Per-modelo before/after kill-rate (mul/div scalar surface)

| Ruleset                  | Before claimed | Before empirical | After empirical (post-fix) |
| :----------------------- | -------------: | ---------------: | -------------------------: |
| `modelo_100.2024`        |        100 %   |             0 %  |     15 % (3 of 20 covered) |
| `modelo_100.2025`        |        100 %   |             0 %  |     15 %                   |
| `modelo_100.2026`        |        100 %   |             0 %  |     15 %                   |
| `modelo_200.{24,25,26}`  |        100 %   |           100 %  |    100 %                   |
| `modelo_202.2025`        |        100 %   |           100 %  |    100 %                   |
| `modelo_303.{24,25,26}`  |        100 %   |           100 %  |    100 %                   |
| All others (no mul/div)  |        100 %   |             N/A  |    N/A                     |

The 90 % floor is preserved because the 51 uncovered M100 leaves are
moved to `mul_div_scalar_deferred` and excluded from the denominator.
Aggregate kill-rate (post-fix) on the claimed-covered surface = 100 %
(7 + 9 = 16 of 16 covered). Aggregate coverage (post-fix) on the full
populated surface = 16 of 67 ≈ 24 % — visibly imperfect, surfaced in
the catalogue, tracked by follow-up issue.

### Per-modelo before/after sub_op coverage

| Ruleset                  | Before claimed (catalogue) | Before empirical | After empirical |
| :----------------------- | -------------------------: | ---------------: | --------------: |
| `modelo_100.2024`        |              71 (catalogue)  |          0 outer |         2 outer |
| `modelo_100.2025`        |              71              |          0 outer |         2 outer |
| `modelo_100.2026`        |              71              |          0 outer |         2 outer |
| `modelo_100.summary.2025`|               3              |     1 outer (0720) |    1 outer (unchanged) |
| `modelo_130.{24,25,26}`  |               8 (each)       |          6 outer |    6 outer (unchanged) |
| `modelo_131.{24,25,26}`  |               5 (each)       |          3 outer |    3 outer (unchanged) |
| `modelo_303.{24,25,26}`  |               2 (each)       |          2 outer |    2 outer (unchanged) |
| Other rulesets           |                    unchanged |        unchanged |       unchanged |

(`sub_op` does not feed the aggregate kill-rate floor, so the
"before" numbers are catalogue-only. The empirical column is what
`test_operand_swap_mutation` actually exercises.)

## Alternatives considered

### A1 — Make the aggregator iterate every populated node and run the mutation in-line

Rejected: would duplicate the mutation logic from each per-class
harness, violating DRY and creating two sources of truth. The
chosen approach (introspect per-class harness param tables) keeps
each harness as the single owner of its mutation logic.

### A2 — Add `pytest` collection introspection

Rejected: importing `pytest` collection results into a
collection-time aggregator is fragile (depends on collection
order, plugin behaviour). The `_build_*` generator pattern is
explicit and order-independent.

### A3 — Drop the kill-rate floor; rely on per-class fail-fast only

Rejected: the floor exists to detect future ruleset PRs that bump
populated counts without extending the per-class harness — exactly
the failure mode this ADR fixes. Dropping the floor would erase
that defense.

### A4 — Cover all 60 M100 mul/div scalar leaves in this PR

Rejected as out of scope. The issue prescribes "≥ 1 fixture per
year" covering the 3 named archetypes. Comprehensive coverage
requires fixtures driving every bracket of every progressive_tarifa
application across Anexo G — a project of its own. The deferred-
coverage pattern documents the gap; the follow-up issue tracks
closing it.

## Acceptance criteria (mirrors the handover prompt's STEP 6)

- Vault research / ADR / plan / exec / summary all written under
  the `2026-04-29-mutation-harness-fix` slug.
- Tautology root cause documented in this ADR; fix lands in the
  aggregator + per-class harnesses + new regression test.
- M100 mul/div scalar fixtures: 3 archetypes × 3 years × 2
  directions = 18 parametrised cases (added to `test_scalar_mutation.py`).
- M100 sub_op fixtures: 2 archetypes × 3 years = 6 parametrised
  cases (added to `test_operand_swap_mutation.py`).
- `_mutate_outer_sub_op` generalised to descend through
  `ClampPositiveFormula`.
- `EXPECTED_COUNTS` rows updated with `mul_div_scalar_deferred` and
  `sub_op_deferred` columns; deferred counts match empirical gap.
- New regression test `test_mutator_tautology_regression.py`
  enforces `populated - empirical_coverage == declared_deferred`.
- Coverage floor 60 % preserved on `src/aeat` via `just test-cov`.
- `just lint && just typecheck && just test && just hooks` all
  green on Windows post-rebase.
- `git log origin/main..HEAD --oneline` shows ONLY #457 commits
  before the PR is opened.
- Follow-up issues filed at PR-open time covering the remaining
  M100 mutation gap (one issue for mul/div scalar, one for sub_op).
