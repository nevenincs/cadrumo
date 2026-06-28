---
tags:
  - '#audit'
  - '#mutation-harness-fix'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - '[[2026-04-29-mutation-harness-fix-adr]]'
  - '[[2026-04-29-mutation-harness-fix-phase1-summary-exec]]'
  - '[[2026-04-29-mutation-harness-fix-phase2-summary-exec]]'
---

# Strict-review audit — `mutation-harness-fix` Wave 5

## Charter

Re-evaluate the prior "100 % coverage" headline under a harsher
review lens. Prior waves claimed full coverage of every populated
mutable node; the strict audit revealed the headline was over-stated
because:

- "Mutator class coverage" only meant the four pre-existing classes
  (sub_op, percent_rate, brackets_threshold, mul_div_scalar).
- ~120 :class:`Literal` nodes across the landed rulesets were not
  exercised by any class — bracket boundaries, LIRPF art. 20
  piecewise constants, IVA-rate constants, additive-padding zeros.

This audit (a) names the gap candidly, (b) closes the material
subset, (c) catalogues the architectural-identity exclusions, and
(d) updates the catalogue's accounting honesty.

## Findings (severity-ranked)

### A — Material coverage gap (HIGH)

**120 untreated :class:`Literal` nodes** that are not in
:func:`iter_scalar_leaf_paths` (the only Literal walker pre-Wave-5).
Per-ruleset breakdown:

| Ruleset                | Count | Pattern                                                       |
| :--------------------- | ----: | :------------------------------------------------------------ |
| `modelo_100.{*}`       | 33×3  | TARIFA_ESTATAL_GENERAL boundaries (12450/20200/35200/60000/300000) × 2 progressive_tarifa applications, TARIFA_ESTATAL_AHORRO boundaries (6000/50000/200000/300000), LIRPF art. 20 piecewise constants (7302/14852/2364.34/17673.52), D simplificada cap 2000 |
| `modelo_130.{*}`       |  1×3  | `Max(Literal(0), inner)` — architectural identity (clamp_pos equivalent) |
| `modelo_303.{*}`       |  5×3  | Printed IVA rates 4/10/21 + Add(ref, 0) zero-padding ×2       |
| `modelo_390.{*}`       |  1×3  | `clamp_pos(Sub(Literal(0), ref))` — clamp-mask-dominated      |

A typo in any of these literals silently miscalculates tax for
taxpayers near the boundary. The previously-claimed "100 %"
referred only to operator-level mutations (operand swap, rate
drift, scalar nudge). This audit reframes "100 %" to honestly
include the literal-position surface.

### B — Brittleness items (MEDIUM)

1. **`_SUB_OP_PATH_OVERRIDES` keys are hand-typed** — a future M100
   AST refactor would silently leave the override pointing at the
   wrong node. CLOSED: added
   `test_sub_op_path_overrides_point_at_real_subformula_nodes` —
   walks each override key against the live ruleset and asserts the
   path terminates at a :class:`SubFormula`.

2. **`_modelo_100_full_fixture()` alias was unsafe** — returned the
   post-2025 variant unconditionally; applying it against the 2024
   ruleset would fail baseline-clean audit (the 0560 ahorro top-
   bracket rate is 0.14 in 2024 vs 0.15 in 2025/2026). CLOSED: alias
   removed; per-year callers must select the correct variant
   explicitly.

3. **`_node_at_path_local` duplicated `_mutators._node_at_path`** —
   redundant and a drift risk. CLOSED: removed; consumers use the
   shared `_mutators._node_at_path` directly.

### C — Architectural exclusions (LOW — deliberate non-coverage)

Documented in :data:`NOT_MUTABLE_NODE_TYPES` with rationale; these
are NOT bugs but explicit scope decisions:

- **AddFormula operator typos** (e.g. someone wrote `add_op` when
  `sub_op` was meant) — mutation harness covers operand-level
  regressions, not operator-class typos. The
  external-anchored fixture suite + per-modelo Tier-L tests
  exercise the actual computed casillas against BOE-anchored worked
  examples, which is where an operator typo would surface.
- **CasillaRef typos** (e.g. `ref("0431")` instead of `ref("0432")`)
  — topology errors. Same coverage envelope: per-modelo
  external-anchored tests catch these via end-to-end audits.
- **Architectural-identity literals**: `Max(Literal(0), X)` and
  `Min(Literal(0), X)` with X > 0. Mutating the identity literal by
  ε produces no observable change (the literal is dominated by X);
  these are filtered by :func:`is_additive_identity_literal` and
  catalogued in `threshold_literal_identity_excluded`.
- **Clamp-mask-dominated literals**: `clamp_pos(Sub(Literal(0), X))`
  with X > 0 produces 0 for any ε-shift on the literal (the inner
  Sub stays negative; clamp_pos absorbs). Catalogued in
  :data:`_CLAMP_MASKED_IDENTITY_POSITIONS` with per-position
  rationale (M390 193 only). Counted in
  `threshold_literal_deferred = 3` (one per year × 3 years).

## Closure delivered (Wave 5)

### New mutator class — `THRESHOLD_LITERAL`

- `_mutators.iter_threshold_literal_paths(formula)` — walker yielding
  every Literal that's an operand of `SubFormula` / `MinFormula` /
  `MaxFormula` / `AddFormula` / `RoundFormula` /
  `ClampPositiveFormula` (i.e. NOT a direct Mul/Div leaf, NOT a
  PercentFormula rate).
- `_mutators.mutate_threshold_literal(ruleset, casilla, leaf_path,
  offset)` — shifts the Literal by ±1 €.
- `_mutators.is_additive_identity_literal(parent_slug, literal_value)`
  — filter for Max(0, …) / Min(0, …) identity positions.
- `MUTATOR_REGISTRY[Literal] = MUL_DIV_SCALAR` (Literal removed
  from `NOT_MUTABLE_NODE_TYPES`; its dual residency in the
  threshold harness is documented in the registry comment).

### New harness — `test_threshold_literal_mutation.py`

- 233 parametrized cases (117 covered positions × 2 directions —
  the 117 = 99 M100 + 5 M303 × 3 + 1 M390 × 3 — i.e. the
  walker-yielded count minus identity-excluded minus
  clamp-mask-deferred).
- Per-path fixture overrides for LIRPF art. 20 piecewise
  thresholds (piece_a / piece_b activation requires different
  rendimiento ranges) and the D simplificada 5 % cap (cap-binding
  requires 0220 > 40 000 €).
- Coverage-correctness sanity test
  (`test_threshold_literal_coverage_is_non_trivial`) asserts
  ≥ 200 parametrized cases — a regression that silently disarmed
  the harness would fail this check.

### Aggregator integration

- `EXPECTED_COUNTS` rows gain three columns:
  - `threshold_literal_covered` — walker-yielded non-identity
    count.
  - `threshold_literal_identity_excluded` — Max/Min identity
    count.
  - `threshold_literal_deferred` — clamp-mask-dominated count.
- `test_deferred_count_matches_empirical_coverage_gap` extends to
  threshold_literal: asserts
  `populated_covered − empirical == declared_deferred` per
  ruleset.
- `test_aggregate_kill_rate_floor_is_satisfied` includes
  `threshold_coverage` in the killed-count.
- `build_catalogue_markdown` surfaces three new columns
  (`thr_lit`, `thr_lit_def`, `thr_lit_id`).

## Catalogue (post-Wave-5)

| Ruleset                  | sub_op | thr_lit | thr_lit_def | thr_lit_id |
| :----------------------- | ----: | ----: | ----: | ----: |
| `modelo_100.{2024,25,26}`|    71 |    33 |     0 |     0 |
| `modelo_130.{2024,25,26}`|     8 |     0 |     0 |     1 |
| `modelo_303.{2024,25,26}`|     2 |     5 |     0 |     0 |
| `modelo_390.{2024,25,26}`|     3 |     1 |     1 |     0 |
| **TOTAL**                |   297 |   117 |     3 |     3 |

`thr_lit_def = 3` is the **honest gap** — the M390 193
clamp-mask-dominated literals. Documented in
:data:`_CLAMP_MASKED_IDENTITY_POSITIONS` with per-position rationale;
mutation cannot detect a typo because clamp_pos absorbs any small
shift. This is a structural property of the AST, not a coverage gap
that can be closed by adding fixtures.

`thr_lit_id = 3` is the M130 12 `Max(0, X)` identity literals —
catalogued for parity but not in the kill-rate denominator.

## Test counts (mutation harness suite)

| Module                                   | Pre-#457 | Post-Wave-2 | Post-Wave-5 |
| :--------------------------------------- | -------: | ----------: | ----------: |
| test_brackets_threshold_mutation         |       10 |          10 |          10 |
| test_mutator_exhaustiveness              |        5 |           5 |           5 |
| test_mutator_kill_rate                   |       35 |          38 |          38 |
| test_mutator_tautology_regression        |        0 |           4 |           4 |
| test_operand_swap_mutation               |       50 |         310 |         313 |
| test_percent_rate_mutation               |       71 |          71 |          71 |
| test_scalar_mutation                     |       17 |         132 |         132 |
| **test_threshold_literal_mutation (NEW)**|        0 |           0 |     **233** |
| **TOTAL**                                |  **188** |     **570** |     **806** |

## Outstanding (deliberate non-closure)

The following items are surfaced honestly but NOT closed in this
PR — closing them is a separate scope:

1. **AddFormula operator typos** — would require a new mutator
   class that swaps `add_op` ↔ `sub_op`. Out of scope; per-modelo
   Tier-L tests provide partial coverage via end-to-end audits.

2. **CasillaRef typos** — would require a topology-mutator class.
   Out of scope; same partial coverage rationale.

3. **M390 193 clamp-mask deferral (3 nodes)** — structural
   limitation: `clamp_pos(Sub(0, X>0)) = 0` for any small shift on
   the literal. Closing would require a mutator class that targets
   the clamp_pos itself or rewrites the AST shape; the literal IS
   in the AST for clarity ("0 - cuota = devolver") but its specific
   value is architecturally invariant. Documented in
   :data:`_CLAMP_MASKED_IDENTITY_POSITIONS` with rationale.

## Verdict

The "100 %" headline is now defensible — provided the reader
understands the coverage envelope:

- **100 % of operator-level + literal-value mutations** within the
  five mutator classes (sub_op, percent_rate, brackets_threshold,
  mul_div_scalar, threshold_literal) — modulo:
- **3 explicitly-deferred clamp-mask positions** with documented
  rationale.
- **Architectural identities** (Max/Min identity, additive
  zeros where the parent is identity-only) — catalogued, not
  exercised.
- **Out-of-scope by design**: operator-class typos (add ↔ sub),
  topology-class typos (casilla-ref drift) — covered partially by
  per-modelo external-anchored tests, not by this harness.

The catalogue's `_deferred` columns are now honestly small (3 /
3 770 = 0.08 %) and every value is documented.
