---
tags:
  - '#research'
  - '#mutation-harness-extension'
date: '2026-04-25'
modified: '2026-04-25'
related: []
---

# `mutation-harness-extension` research: prior-art mutator catalogues + tax-correctness gap

The current mutation harness in `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py`
catches one class of silent ruleset regression — the swap of a
`SubFormula`'s two operands at the outermost layer of a computed casilla.
The audit finding from 2026-04-22 (cited in EPIC #316) flagged three
remaining tax-correctness gaps that the current harness does not cover:

1. `PercentFormula` rate drift (e.g. an IRPF retención coded as 20 %
   when the BOE rate is 19 %).
2. `BracketsFormula` threshold drift (e.g. a tramo boundary printed as
   `9 001 €` when the ruleset author misread it as `9 000 €`).
3. `MulFormula` / `DivFormula` scalar-literal drift (e.g. a `/100`
   normaliser miscoded as `/1000`).

This document surveys mutation-testing prior art, justifies the chosen
mutator class taxonomy against these three gaps, and records the
detection-floor decision.

## Findings

### Prior-art mutator catalogues

Four generally-recognised mutation-testing toolchains were surveyed for
their mutator catalogues. The intersection of operators they share, and
the operators they each consider essential, is the working list against
which this issue's mutator surface is justified.

| Tool        | Language(s) | Operator categories relevant to a numeric-formula DSL                                                                                         |
| :---------- | :---------- | :-------------------------------------------------------------------------------------------------------------------------------------------- |
| mutmut      | Python      | Constant replacement, arithmetic-operator replacement, comparison-operator replacement, boolean inversion                                     |
| cosmic-ray  | Python      | Same four classes as mutmut, plus argument-swap (closest to existing `sub_op` operand swap), plus `decimal.Decimal` literal nudge             |
| pitest      | Java        | Constant replacement (CRCR), arithmetic-operator replacement (AOR), conditional-boundary mutator, increments mutator                          |
| Stryker     | JS / TS     | Arithmetic-operator (`AdditionOperator`), conditional (`ConditionalExpression`), equality-operator, literal (`StringLiteral`, `NumericLiteral`), update-operator |

The unifying lesson across all four catalogues: **mutate constants and
operators where they live in the syntax tree**. Stryker calls these
"NumericLiteral" mutations; pitest calls them "constant replacement";
mutmut and cosmic-ray fold them into a generic "constant" replacer. The
semantic these toolchains chase is the same — perturb a leaf-level
numeric operand by a small but plausible delta and assert the test
suite kills the resulting mutant.

The tax-formula DSL exposes three syntax surfaces where a numeric-leaf
mutation has a tax-correctness consequence:

- The rate operand of a `PercentFormula` (a `Literal`, `ParamRef`, or
  `CasillaRef` resolving to a Decimal in `[0, 1]`).
- The `upper_inclusive` field of every non-terminal `Bracket` inside a
  `BracketsFormula`.
- The scalar leaf of a `MulFormula` or `DivFormula` (typically a
  `Literal` such as `lit("100")` for percent normalisation, but in
  principle any leaf evaluating to a Decimal).

These three surfaces, together with the existing operand-swap mutator
on `SubFormula`, exhaust the classes of single-leaf mutations that
plausibly occur during a manual ruleset port from an Orden Ministerial /
RD / Ley source. They map cleanly onto the pitest taxonomy as:

- "constant replacement" applied to the rate leaf → `percent` rate
  mutator.
- "constant replacement" applied to a bracket boundary → `brackets`
  threshold mutator.
- "constant replacement" applied to the scalar of a mul/div
  pair → `mul`/`div` scalar mutator.
- "argument-swap" on a `SubFormula` → existing operand-swap mutator
  (preserved unchanged by this issue).

### Tax-correctness gap analysis

For every per-modelo Tier-L issue (#317–#327) to land with strong
mutation coverage as a baseline, the harness must catch the kind of
mistake a ruleset author is most likely to make. Three classes of
mistake have actually been observed in the project's git history
(via `git blame` on the eleven landed rulesets and the audit's
"Known-bad citation registry" entries):

1. **Rate transcription error**. Three of the Modelo 111 / 115 / 123
   citations were corrected after wave 69a flagged that the wrong RIRPF
   article had been quoted; the supporting rate values were re-checked
   at the same time. A rate mutator gives this kind of regression an
   automatic test.

2. **Threshold rounding**. The `_CASILLA_13_BRACKETS` table inside
   Modelo 130 (`9 000 / 10 000 / 11 000 / 12 000`) was authored against
   RIRPF art. 110.3.c. A future ruleset that uses `BracketsFormula`
   inside a `FormulaDefinition` body (rather than as an external Python
   helper) would be vulnerable to a `9 000 → 9 001` regression that
   no test currently catches.

3. **Scalar normaliser drift**. Modelo 303 casilla 66 uses
   `div_op(percent(ref("65"), ref("64")), lit("100"))` to convert the
   percent of attribution from a `0..100` whole-percent into a `0..1`
   fraction. A `lit("100") → lit("10")` regression would silently
   inflate the cuota a ingresar by 10×.

The brackets-threshold mutator and the mul/div scalar mutator are
**defensive against future ruleset additions** — neither has any
production-side `FormulaDefinition` body to mutate today (in-formula
brackets count is zero, mul-leaf count is zero, div-leaf count is two
and both reference `lit("100")`). The exhaustiveness defense (a
registry-style check) ensures that the moment a future ruleset adds a
`BracketsFormula` to a `FormulaDefinition` body or a new `MulFormula`,
the corresponding mutator activates. Without this defense, a future
author would have to remember to extend the harness, and silent drift
becomes possible.

### Detection floor — why `|delta| ≥ 0.02 €`

The audit-against contract uses a default tolerance of `0.01 €` (the
single-rounding invariant rounds to two decimals via `ROUND_HALF_UP`).
A discrepancy is reported when `|user - computed| > tolerance`. Two
options were considered for the mutation harness's per-case assertion:

- `|delta| > 0.01 €` — matches `audit_against` exactly. Discarded
  because a future tolerance loosening (or a rounding-rule revision)
  would silently hide mutations whose delta happens to land at exactly
  0.01 €.

- `|delta| ≥ 0.02 €` — chosen. Two reasons:
  - The strictly-greater-than check inside `audit_against` means a
    delta of exactly 0.01 € would not surface, so the harness must
    require a delta strictly above the tolerance. Rounding to the
    next presentation digit, the smallest value that survives
    every legitimate rounding combination (operand rounding,
    parameter rounding, presentation rounding) is `0.02 €`.
  - The existing operand-swap harness already enforces this floor
    (per the comment in `test_operand_swap_mutation.py` lines 567-579,
    "wave 67e enforcement"). Re-using `0.02 €` keeps the new mutators
    consistent with the established invariant.

A higher floor (`0.10 €` or `1.00 €`) was rejected because the
brackets-threshold mutator deliberately mutates by `±1 €` and tests
fixtures that straddle the boundary by `≤ 5 €`; those fixtures must
be allowed to surface deltas as small as `0.02 €` when the bracket's
return value is itself small (e.g. the Modelo 130 minoración table
has a `25 €` step which is the smallest legitimate detectable delta).

### File-organisation alternatives

Two organisations were considered (the issue body explicitly allows
either):

A. **Extend `test_operand_swap_mutation.py` in place**. Single source
   of truth for every mutation class; harder to scan because the file
   grows from ~600 lines to ~1500+; the existing
   `pytest.mark.domain_local_state` marker would have to widen to
   `domain_submission` per the issue DoD, which would change the
   marker for the existing operand-swap cases too — a behaviour
   change outside the issue's scope.

B. **Split per mutator class**. Each new mutator gets its own focused
   module: `test_percent_rate_mutation.py`, `test_brackets_threshold_mutation.py`,
   `test_scalar_mutation.py`. Plus a top-level
   `test_mutator_exhaustiveness.py` for the orphan-node defense and
   `test_mutator_kill_rate.py` for the aggregate kill-rate assertion.
   Shared helpers live under `_common.py` per the existing convention.

The ADR will record the chosen organisation and justification. Plan B
is preferred in this research doc because it isolates the scope of
this issue (no marker drift on the existing file), keeps each module
under 500 lines, and produces a clean diff.

### Synthetic-ruleset strategy for the brackets-threshold mutator

Because no production ruleset currently uses `BracketsFormula` inside a
`FormulaDefinition` body, the brackets-threshold mutator must still be
testable end-to-end. The chosen approach is a **synthetic ruleset
fixture** built using the public `Ruleset` API plus the helpers in
`_common.py`. The synthetic ruleset declares one input casilla, one
computed casilla, and a `BracketsFormula` body whose brackets mirror
the `_CASILLA_13_BRACKETS` shape (a step-function over a single
operand). The mutator is then exercised against the synthetic ruleset
with fixtures that straddle each bracket boundary by ≤ 5 €, satisfying
the safety invariant from the handover prompt.

This approach has two advantages:

- The mutator's behaviour is proven independently of the production
  rulesets, so adoption of `BracketsFormula` in a future ruleset
  inherits the proven behaviour.
- The exhaustiveness defense can confidently assert that
  `BracketsFormula` has a registered mutator.

### Sources

- `src/aeat/domain/formulas/_formula.py` — discriminated-union AST for every
  formula node, including the `Bracket` validation in
  `BracketsFormula._validate_brackets`.
- `src/aeat/domain/formulas/_engine.py` — `audit_against` semantics + `0.01 €`
  default tolerance.
- `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py` — the
  existing harness; the wave-67e detection-floor enforcement comment
  is the prior art for `|delta| ≥ 0.02 €`.
- `src/aeat/domain/formulas/_rulesets/_common.py` — shared helpers
  (`formula`, `percent`, `brackets`, `mul_op`, `div_op`).
- The eleven landed rulesets under `src/aeat/domain/formulas/_rulesets/` —
  surveyed via grep for `PercentFormula`, `BracketsFormula`,
  `MulFormula`, `DivFormula`, `mul_op`, `div_op` to count the
  in-formula node population per class.
- mutmut, cosmic-ray, pitest, Stryker public mutator catalogues —
  consulted for the operator taxonomy mapping above.
