---
tags:
  - '#research'
  - '#mutation-harness-fix'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-25-mutation-harness-extension-research]]'
  - '[[2026-04-25-mutation-harness-extension-adr]]'
---

# `mutation-harness-fix` research — kill-rate aggregator tautology + M100 mutation gap

## Context

PR #448 (the M100 RENTA megaproject — closing #317 / #341 / #342 / #343 / #344)
landed full-form `modelo_100.{2024,2025,2026}` rulesets with 71 `sub_op`
nodes and 20 `mul/div` scalar leaves per year. Each year was added to
`EXPECTED_COUNTS` in `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`,
yet none of the per-class mutation harnesses (`test_scalar_mutation.py`,
`test_operand_swap_mutation.py`) were extended to import the new
rulesets. The aggregate kill-rate test continued to report 100 %
because its `killed = populated` line is structurally unconditional.

Issue #457 surfaces this as a **tautology** in the aggregator's
arithmetic — `killed = populated` makes the assertion vacuous on any
node that lives in `EXPECTED_COUNTS` but is not enumerated by a
per-class harness. Today that gap is 60 mul/div scalar leaves and
213 `sub_op` nodes from the M100 megaproject. Tomorrow it will be
whichever per-modelo Tier-L PR lands without extending the harness.

## Findings

### Tautology root cause (`test_mutator_kill_rate.py:435-470`)

```python
def test_aggregate_kill_rate_floor_is_satisfied() -> None:
    populated = 0
    catalogued_unflagged = 0
    for _ruleset_id, counts in EXPECTED_COUNTS.items():
        populated += counts["percent_rate_literal"]
        populated += counts["percent_rate_param"]
        populated += counts["mul_div_scalar"]
        catalogued_unflagged += counts["percent_rate_compound_skipped"]
        catalogued_unflagged += counts["percent_rate_casilla_ref_skipped"]
    populated += 4              # synthetic brackets
    assert populated > 0
    killed = populated          # ← tautology
    kill_rate = Decimal(killed) / Decimal(populated)
    assert kill_rate >= Decimal("0.90")
```

The doctstring rationalises the equality with: *"All populated nodes
are killed in their respective test modules (any failure there would
have failed this session before reaching here)."* That is true only
for nodes the per-class harnesses actually parametrise. Nodes
**counted in EXPECTED_COUNTS but not enumerated** by any per-class
test sail past every assertion: per-class tests don't try to mutate
them (they are not in any param table) and the aggregate test
declares them killed by fiat.

### Concrete gap exposed by the M100 megaproject

The walker `_count_per_ruleset` populates `EXPECTED_COUNTS` rows by
visiting every `Formula` in the ruleset and classifying its nodes via
`iter_compound_descendants`, `iter_percent_nodes`,
`iter_brackets_nodes`, and `iter_scalar_leaf_paths` from `_mutators.py`.
For `modelo_100.<año>` (any year), those walkers find:

- **71 `SubFormula` descendants** (Anexo G `cuota_diferencial` chain
  at casilla 0720, Anexo F `base_liquidable_general` at 0545,
  per-anexo intermediate sub_op chains).
- **20 `Mul`/`Div` literal leaves**: 17 in Anexo G's `progressive_tarifa`
  bracket-rate `MulFormula(Literal(rate), portion)` constructions
  (TARIFA_ESTATAL_GENERAL × 1 + TARIFA_ESTATAL_GENERAL on minimo × 1
  + TARIFA_ESTATAL_AHORRO × 1 = 3 progressive applications minus the
  one rate that is 0 in the AST yields 17 `MulFormula(Literal(rate),
  portion)` nodes); 2 in Anexo B1 (`mul_op(lit("1.75"), …)` and
  `mul_op(lit("1.14"), …)` for the LIRPF art. 20 piecewise reducción);
  1 in Anexo D simplificada (the 5 % cap `mul_op(lit("0.05"), …)`).

The corresponding per-class harness imports:

| Harness                         | Imports M100 full?           | M100 nodes mutated         |
| :------------------------------ | :--------------------------- | :------------------------- |
| `test_scalar_mutation.py`       | No (only M303 / M200 / M202) | 0 of 60                    |
| `test_operand_swap_mutation.py` | No (only M100_SUMMARY_2025)  | 0 of 213                   |
| `test_percent_rate_mutation.py` | N/A — M100 has no `Percent`  | 0 of 0 (correctly excluded) |

The `test_aggregate_kill_rate_floor_is_satisfied` denominator counts
the 60 mul/div scalar leaves toward `populated`. The numerator says
`killed = populated`. Empirical truth: 7 of 67 mul/div scalar nodes
are mutated → kill-rate ≈ 10.4 %. The 90 % floor is "satisfied" only
because of the tautology.

`sub_op` is *not* in the kill-rate denominator (it is enforced by
`test_operand_swap_mutation` per-test rather than by the aggregate
floor), so M100's 213 uncovered `sub_op` nodes do not corrupt the
aggregate kill-rate computation. They do still affect the catalogue
markdown produced by `build_catalogue_markdown` — readers see "71
sub_op nodes" against M100 and infer they're tested.

### Per-modelo true kill-rate (BEFORE FIX, mul/div scalar only)

Counted by walking each ruleset's `_FORMULAS` with
`iter_scalar_leaf_paths` and intersecting against the
`test_scalar_mutation.py::_build_test_params()` parameter table:

| Ruleset                  | populated mul/div | actually mutated | kill-rate |
| :----------------------- | ----------------: | ---------------: | --------: |
| `modelo_100.2024`        |                20 |                0 |     0 %   |
| `modelo_100.2025`        |                20 |                0 |     0 %   |
| `modelo_100.2026`        |                20 |                0 |     0 %   |
| `modelo_100.summary.2025`|                 0 |                0 |     N/A   |
| `modelo_111.{24,25,26}`  |                 0 |                0 |     N/A   |
| `modelo_115.{24,25,26}`  |                 0 |                0 |     N/A   |
| `modelo_123.{24,25,26}`  |                 0 |                0 |     N/A   |
| `modelo_130.{24,25,26}`  |                 0 |                0 |     N/A   |
| `modelo_131.{24,25,26}`  |                 0 |                0 |     N/A   |
| `modelo_180.{24,25,26}`  |                 0 |                0 |     N/A   |
| `modelo_200.{24,25,26}`  |                 1 |                1 |   100 %   |
| `modelo_202.2025`        |                 1 |                1 |   100 %   |
| `modelo_303.{24,25,26}`  |                 1 |                1 |   100 %   |
| `modelo_390.{24,25,26}`  |                 0 |                0 |     N/A   |
| **TOTAL**                |              **67** |            **7** | **10.4 %** |

Aggregator-claimed: 100 %. Empirical: 10.4 %. Inflation: ~9.6×.

### `_mutate_outer_sub_op` brittleness for clamp-wrapped chains

The helper in `test_operand_swap_mutation.py:82-115` assumes
`FormulaDefinition.formula` is a `RoundFormula(SubFormula(...))`:

```python
round_node = fd.formula
if not isinstance(round_node, RoundFormula): raise TypeError(...)
inner = round_node.operands[0]
mutated_inner = _swap_sub_op(inner)   # raises if `inner` is not SubFormula
```

For M100 casilla 0545 (base_liquidable_general) the body is
`clamp_pos(sub_op(sub_op(...)))`, i.e. `RoundFormula(ClampPositiveFormula(SubFormula(...)))`.
`inner` is `ClampPositiveFormula`, not `SubFormula`, so the helper
raises `TypeError`. The same applies to M100 0550 (cuota integra
estatal general = `clamp_pos(sub_op(...))`) and 0698 (cuota líquida =
`clamp_pos(sub_op(sub_op(...)))`), and to M390 193
(`clamp_pos(sub_op(0, 191))`). Issue #457 explicitly prescribes a
fixture for 0545, so the helper must be generalised to descend
through `ClampPositiveFormula` to find the underlying `SubFormula`.

### Per-class harness shape — `iter_<class>_targets` is implicit

Each per-class test module exposes a `_build_test_params()` (scalar,
percent, brackets) or a `pytest.mark.parametrize` literal block
(operand-swap) that enumerates the full set of mutated targets. The
aggregator can introspect those by importing the relevant generators
and counting unique `(ruleset_id, casilla_id, leaf_path | param_id |
target_casilla)` tuples. This is the natural shape for the
"empirical killed count" the issue's AC asks for.

### The "deferred coverage" pattern is already in the codebase

Two `EXPECTED_COUNTS` columns — `percent_rate_compound_skipped` and
`percent_rate_casilla_ref_skipped` — are already excluded from the
kill-rate denominator with documented rationale (compound-rate
mutations delegate to descendants; casilla-ref rates are out-of-AST
inputs). The same pattern can be extended for nodes whose per-class
harness coverage has been deliberately deferred to a follow-up
issue: a `mul_div_scalar_deferred` column documents the gap, the
aggregator subtracts it from the denominator, and the deferred
count is asserted against the empirical gap (so a future PR cannot
silently grow the deferred set without extending the per-class
harness).

## Decisions

The ADR will record:

1. **Aggregator computes `killed` empirically** by importing each
   per-class harness's parameter generator and counting unique
   targets. The current `killed = populated` line is removed.

2. **`EXPECTED_COUNTS` gains `<class>_deferred` columns** for nodes
   whose per-class coverage is deliberately deferred (with follow-up
   issue link). The aggregator subtracts these from the denominator
   so the 90 % floor is computed on the **claimed-covered surface**
   only.

3. **A new assertion** binds the deferred count to the empirical gap:
   `populated_total - populated_under_test == sum_of_deferred_counts`.
   A future PR that bumps `EXPECTED_COUNTS` without either extending
   the per-class harness OR catalogueing the gap as deferred fails
   loudly.

4. **`_mutate_outer_sub_op` descends through `ClampPositiveFormula`**
   to support M100 0545 (and the analogous M100 0550 / 0698, M390 193
   if a future fixture wants them).

5. **M100 mul/div scalar fixtures**: per the issue, ≥ 1 fixture per
   year covering one TARIFA_ESTATAL_GENERAL rate (e.g. the 22.5 %
   bracket on 60k–300k), one TARIFA_ESTATAL_AHORRO rate (the 14 %→15 %
   delta point in the top bracket), and one LIRPF art. 20 slope (1.75
   in piece_a OR 1.14 in piece_b). 9 mutations × 2 directions = 18
   parametrised mul/div scalar M100 cases.

6. **M100 sub_op fixtures**: per the issue, ≥ 1 fixture per year
   covering 0720 (cuota_diferencial direct sub_op chain, Round-wrapped)
   and 0545 (base_liquidable_general clamp_pos-wrapped sub_op chain).
   6 outer-swap M100 cases.

7. **Tautology regression test** (`test_mutator_tautology_regression.py`):
   constructs a synthetic minimal scenario where `EXPECTED_COUNTS`
   is bumped without extending the per-class harness AND without
   declaring the bump as deferred — asserts the new aggregator
   surfaces the gap (where `killed = populated` would have hidden it).

8. **Follow-up issue filed** for the remaining M100 mul/div scalar
   gap (51 of 60 leaves still uncovered after the prescribed
   3-fixtures-per-year addition) and the M100 sub_op gap (207 of 213
   nodes still uncovered after the prescribed 2-fixtures-per-year
   addition). The deferred catalogue documents the gap; the follow-up
   issue tracks closing it.

## Plan

The implementation pipeline:

- **Plan** captures the file-level change list, ordering, and the
  PR-prep rebase-out-#216 step. Phase boundaries: harness mechanics
  (operand-swap helper extension), aggregator refactor, M100 fixture
  additions, regression-defense test, vault exec records.

- **Execution** runs in the order: helper generalisation →
  aggregator refactor → M100 scalar fixtures → M100 sub_op fixtures
  → regression-defense test → vault exec records → mandatory
  vaultspec-code-review → rebase-out-#216 → PR open.

- **Code review** asserts the seven safety invariants from the
  handover prompt (tautology fixed, aggregator accuracy, no
  regression, orphan-node defense intact, no mocks, #216 cleanly
  rebased out, test markers preserved).

## Outstanding follow-ups

A separate issue (filed at PR-open time) will track:

- **`#NEW-A: M100 mul/div scalar coverage gap`** — extend the
  scalar harness to cover the remaining ~51 leaves per year (full
  TARIFA_ESTATAL_GENERAL × 6 brackets × 3 progressive applications +
  Anexo D simplificada 5 % cap + any other Anexo F slope literals).

- **`#NEW-B: M100 sub_op coverage gap`** — extend the operand-swap
  harness to cover the remaining 65 sub_op chains per year (every
  per-anexo intermediate sub_op chain). Includes inner-sub_op
  coverage (the existing harness mutates only outer sub_ops; nested
  inner sub_ops at e.g. M130 casilla 07 are also uncovered today
  but that gap pre-dates #457).

- **`#NEW-C: M390 casilla 193 sub_op coverage`** — `clamp_pos(sub_op(0, 191))`
  was uncovered before #457; the helper generalisation makes it
  trivially fixable in a follow-up.
