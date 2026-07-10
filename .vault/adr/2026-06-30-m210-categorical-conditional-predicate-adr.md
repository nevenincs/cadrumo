---
tags:
  - '#adr'
  - '#m210-categorical-conditional-predicate'
date: '2026-06-30'
modified: '2026-07-08'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-adr]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-research]]"
  - '[[2026-07-06-m210-categorical-conditional-predicate-research]]'
---
# `m210-categorical-conditional-predicate` adr: `Categorical-conditional verification predicate for the M210 inmobiliaria branch` | (**status:** `accepted`)

## Problem Statement

`2026-06-30-modelo-verify-nonzero-guards-adr` deliberately scoped the M210
inmobiliaria branch out of its five-modelo `implies_nonzero` sweep: the
branch's silent-zero risk is the highest-value gap of the whole campaign (the
most common M210 filing scenario — a non-resident owning Spanish real estate
with no rental income still owes imputed-rent IRNR) but the trigger is a
categorical equality on `tipo_renta` (`data_type = "text"`,
`src/aeat/_data/registry/aeat/modelos/210/revisions/2025/casillas/0001-casillas.toml:23-31`),
not a numeric antecedent. The shipped `implies_nonzero` DSL operator reads only
`Decimal` casilla values (`casilla_values: Mapping[CasillaId, Decimal]`,
`src/aeat/application/modelo/_verification_actions.py:306-310`), so it cannot
express "when `tipo_renta == "inmobiliaria"`, `base_imponible` must be
non-zero." Plan `2026-06-30-modelo-verify-nonzero-guards-plan` Wave `W02`
Phase `P07` (Steps `S20`-`S23`) requires this gap to be resolved — implemented
if feasible, or formally deferred and tracked, never silently dropped.

## Considerations

- **The base-imponible formula is the formal authority for the inmobiliaria
  branch.** `m210-base-imponible-2025`
  (`src/aeat/_data/registry/aeat/modelos/210/revisions/2025/formulas/0001-m210-base-imponible-2025.toml`)
  resolves `base_imponible` via the `m210_resolve_base_imponible` custom op
  (`src/aeat/domain/calculations/registry/_formula_runtime.py:817-900`). Every
  inmobiliaria-branch input casilla (`valor_catastral`,
  `coeficiente_imputacion_inmobiliaria`, `dias_imputacion`,
  `valor_adquisicion`, `valor_comprobado_administracion`) is
  `required = false`, so an operator who selects `tipo_renta = "inmobiliaria"`
  is never forced to populate any of them.
- **The formula already refuses the worst case, but not the silent one.**
  When both `valor_catastral` and the acquisition/administrative substitute
  are zero, `_evaluate_m210_resolve_base_imponible` raises
  `RegistryValidationError` (`_formula_runtime.py:889-897`) rather than
  computing a silent zero. The genuinely silent path is `dias_imputacion`
  left blank (defaults to `0`) with a valid `valor_catastral` and a matching
  `coeficiente_imputacion_inmobiliaria`: `days_fraction` resolves to `0` and
  `catastral_value * coefficient * days_fraction` evaluates to exactly `0`
  with no validation error (`_formula_runtime.py:866-884`). A taxpayer who
  legitimately owes imputed-rent IRNR can file a zero base with no engine
  signal. The guard therefore targets the general shape ("inmobiliaria implies
  a non-zero base_imponible"), not one specific missing input — narrower
  framings (e.g. "valor_catastral is blank") miss the `dias_imputacion`
  failure mode and several equivalent ones.
- **A parallel text-value channel reaches the verification call site on the
  READ side; the WRITE side that populates it was added by this feature (see
  the post-review correction in Rationale), with zero widening of the
  Decimal-only formula/calculate boundary.**
  `CalculationRevision.input_values_by_casilla_id: Mapping[CasillaId, str]`
  (`src/aeat/domain/modelos/_calculation_revision.py:310`) carries every
  operator-entered raw string, independently of the Decimal
  `casilla_values` projection. `_collect_revision_verification_findings`
  already reads `target.input_values_by_casilla_id`
  (`src/aeat/application/modelo/_verification_actions.py:1207`) at exactly
  the call site that invokes `_evaluate_verification_predicates`
  (`_verification_actions.py:1230-1237`), in the same function, a few lines
  above. The formula-evaluation context independently proves the same shape
  is safe at a different layer: `_EvalContext.text_values` already threads a
  parallel text channel through `m210_resolve_base_imponible`
  (`_formula_runtime.py:828`, `ctx.text_values.get(args.tipo_casilla_id, "")`)
  without touching the Decimal `casilla_values` mapping the rest of the
  formula and calculate machinery depends on. Plumbing
  `target.input_values_by_casilla_id` into the verification predicate
  evaluator is the same pattern at the verification-evaluator boundary: a
  second, additive, optional parameter — no existing `Mapping[CasillaId,
  Decimal]` call site is touched or widened.
- **An asymmetric (ADVISORY-only) operator already has precedent in the
  DSL.** `equals` is registered and validated but has no branch in
  `_evaluate_advisory_predicate_fires`; `advisory_when_ratio_ge` is the
  mirror case — registered and evaluated only in the advisory function, with
  no branch in `_evaluate_predicate_expression`
  (`_verification_actions.py:306-452` vs `:503-575`). No registry-build
  validator anywhere cross-checks an operator name against `finding_kind`. A
  new ADVISORY-only operator with no BLOCKING_RULE branch is therefore
  consistent with the shipped DSL's existing asymmetry, not a new pattern.
- **Registry-build validation for mixed-shape argument lists already has a
  precedent.** `roll_forward_balances` is a four-casilla-id operator with a
  bespoke arity/casilla-existence validator
  (`_roll_forward_balances_predicate_arity_failures`,
  `src/aeat/domain/calculations/registry/_validate_surfaces.py:170-193`)
  rather than routing through the generic
  `_casilla_list_predicate_failures` (which validates every bracketed token
  as a casilla id — wrong for our middle literal token). The new operator's
  validator follows the same bespoke shape.

## Considered options

- **(a) Narrow operator extension at the verification-evaluator boundary
  (chosen).** Add `casilla_equals_implies_nonzero(["antecedent_casilla",
  "literal", "consequent_casilla"])` to `KNOWN_VERIFICATION_PREDICATE_OPERATORS`,
  evaluated only in `_evaluate_advisory_predicate_fires` against a new
  optional `text_values: Mapping[CasillaId, str]` parameter sourced from
  `target.input_values_by_casilla_id`. Zero widening of the Decimal-only
  `casilla_values` mapping anywhere else; the formula engine, the calculate
  path, and every other predicate operator are untouched.
- **(b) Widen `casilla_values` to a heterogeneous `Mapping[CasillaId,
  Decimal | str]`.** Rejected: this is exactly the "Decimal-only plumbing
  constraint" the plan flagged as the blocking risk. `casilla_values` is
  consumed by every other operator in `_evaluate_predicate_expression` /
  `_evaluate_advisory_predicate_fires` via `Decimal(0)` defaults and
  arithmetic comparisons; widening its declared type would force every
  existing branch to defend against a `str` value it cannot arithmetically
  compare, for the benefit of exactly one operator. The aeat-calculation-
  grounding and aeat-architecture-boundaries rules treat this class of
  type-erasure widening as a boundary leak to avoid, not a convenience.
- **(c) Defer to a follow-up research/DSL-extension feature.** Rejected as
  the primary path: the investigation in (Considerations, above) found no
  invasive cross-boundary change is required — the text-value channel
  already reaches the exact call site needed, at the exact layer needed,
  with a working precedent (`m210_resolve_base_imponible`'s `text_values`)
  one file over. Deferring a feasible, narrowly-scoped, low-risk fix for the
  campaign's own highest-value finding would contradict the
  no-silent-under-declaration discipline this campaign exists to uphold.

## Constraints

- The new operator is ADVISORY-only by convention, mirroring the existing
  `equals` (BLOCKING-only) / `advisory_when_ratio_ge` (ADVISORY-only)
  asymmetry. A predicate authored with `finding_kind = "BLOCKING_RULE"` using
  this operator name would fall through `_evaluate_predicate_expression`'s
  unmatched-expression default (`return True`, trivially holding) since no
  BLOCKING branch is implemented — the same latent behaviour the two existing
  asymmetric operators already carry. This ADR records the constraint rather
  than introducing a new cross-cutting `finding_kind`-pairing validator,
  since no such validator exists anywhere in the registry-build surface today
  and adding one here would be a wider change than this Phase's scope.
- `text_values` is threaded as an additive optional keyword parameter
  (default `{}`) on `_evaluate_advisory_predicate_fires` and
  `_evaluate_verification_predicates` / their public aliases
  (`evaluate_advisory_predicate_fires`, `evaluate_verification_predicates`)
  to preserve every existing 3-positional-argument call site across the six
  shipped `test_verification_m*_advisory.py` suites and the M100/M200/M303
  advisory tests.
- The literal comparison is exact-string equality against the operator's
  raw, whitespace-stripped input (`CalculationRevision` strips
  `input_values_by_casilla_id` values at construction,
  `src/aeat/domain/modelos/_calculation_revision.py:175-176`); the predicate
  does not normalise case or accents. `"inmobiliaria"` is already the exact
  literal the `m210_resolve_base_imponible` custom op compares against
  (`_formula_runtime.py:840`), so no new literal vocabulary is introduced.

## Implementation

`casilla_equals_implies_nonzero(["antecedent_casilla_id", "literal",
"consequent_casilla_id"])` is registered in
`KNOWN_VERIFICATION_PREDICATE_OPERATORS` and documented in
`VerificationPredicateDefinition`'s DSL docstring alongside the other
operators. The evaluator branch lives in `_evaluate_advisory_predicate_fires`:
it fires (ADVISORY shown) iff `text_values.get(antecedent_casilla_id) ==
literal` AND `casilla_values.get(consequent_casilla_id, Decimal(0)) ==
Decimal(0)`; any other combination — including a missing antecedent value —
holds (no advisory). `_evaluate_verification_predicates` and its public alias
gain the same additive `text_values` parameter and thread it only into the
advisory branch. `_collect_revision_verification_findings` passes
`target.input_values_by_casilla_id` as `text_values` at its existing call
site. Registry-build validation adds a bespoke
`_casilla_equals_implies_nonzero_predicate_arity_failures` validator in
`_validate_surfaces.py` (mirroring `roll_forward_balances`'s shape): exactly
three tokens, the first and third resolved against the revision's casilla id
set, the middle token required non-empty. The M210 2025 revision's
`verification_expectations/0001-verification_predicates.toml` gains one new
ADVISORY predicate using the operator (`tipo_renta == "inmobiliaria"` implies
`base_imponible` non-zero), grounded in TRLIRNR art. 13.1.h (Spanish-source
imputed-rent classification) and art. 24 (base imponible determination),
appended alongside the two existing predicates (representante-fiscal,
rendimientos-integros-implica-base-imponible) without modifying either.

## Rationale

The Decimal-only-plumbing risk the plan flagged as the blocking constraint
does not, on inspection, block this fix: a parallel text-value channel
(`CalculationRevision.input_values_by_casilla_id`) already reaches the exact
verification call site that needs it, and an existing production code path
(`m210_resolve_base_imponible`'s `ctx.text_values`) proves the same
two-channel pattern is safe one layer over, in the formula engine. Extending

**Post-review correction (2026-07-01).** The code review found that while the
verification layer already READ `target.input_values_by_casilla_id`, nothing
POPULATED it with operator text: the live calculate path
(`calculate_modelo_revision` → `resolve_calculation_inputs` → the CLI
`--casilla ID=VALUE` surface) was Decimal-gated end to end, so `tipo_renta`
(a `data_type = "text"` casilla) could never be set in production and the
inmobiliaria guard could never fire — and the pre-existing
`m210_resolve_base_imponible` inmobiliaria branch was itself dead in
production for the same reason. This feature therefore ADDED the write-side
wiring: a `text_casilla_inputs` channel routed from the CLI
(`_calculate_input.py`, `data_type`-aware `--casilla` routing +
`ModeloCalculateTextInputError`) through
`calculate_modelo_work_revision` and the bucket-aggregation wrappers into
`calculate_modelo_revision`, which now passes `text_inputs=` to
`calculate_registry_snapshot` and merges the canonical text entries into the
persisted `input_values_by_casilla_id`. This both makes the inmobiliaria
advisory reachable and unblocks the pre-existing dead inmobiliaria base
formula. The read-side "already reaches" reasoning above was correct only for
the read half; the write half was the missing plumbing.
the verification-predicate DSL with one new, narrowly-scoped, ADVISORY-only
operator — additive on every signature it touches — closes the campaign's
highest-value finding without widening the Decimal contract any other
operator, the formula engine, or the calculate path relies on.

## Consequences

- **Gains.** The M210 inmobiliaria branch — the modelo's most common
  real-world filing scenario — now surfaces a non-blocking, legally grounded
  alert when an operator selects `tipo_renta = "inmobiliaria"` but the
  computed `base_imponible` resolves to zero, closing the highest-value
  silent-under-declaration gap this campaign identified. The
  `casilla_equals_implies_nonzero` operator is now available to any future
  predicate gated on a categorical (text) casilla equality, not just M210.
- **Difficulties.** The operator is ADVISORY-only by convention rather than
  by an enforced registry-build guard; a future author could mis-declare it
  `BLOCKING_RULE` and the predicate would silently never fire. This mirrors
  pre-existing latent behaviour on `equals` / `advisory_when_ratio_ge` and is
  recorded here as a known, accepted gap rather than a new one.
- **Pitfalls avoided.** Widening `casilla_values` to a heterogeneous type (the
  rejected option (b)) would have forced every other predicate operator to
  defend against a non-Decimal value for the sake of one new operator — a
  type-erasure boundary leak exactly the kind `aeat-calculation-grounding`
  and `aeat-architecture-boundaries` exist to prevent. Deferring (the rejected
  option (c)) would have left the campaign's own highest-value finding
  unresolved despite a feasible, low-risk, narrowly-scoped fix being
  available.

## Codification candidates

- None proposed. This ADR extends the established asymmetric-operator and
  additive-optional-parameter conventions already present in the
  verification-predicate DSL; no new durable cross-session constraint is
  introduced beyond what `no-silent-under-declaration` already requires.
