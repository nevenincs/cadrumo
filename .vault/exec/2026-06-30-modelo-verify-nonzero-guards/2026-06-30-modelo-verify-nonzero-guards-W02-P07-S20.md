---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:66bb5a1c142460431732a5b1389040f91c4d39c9b9458dc343f257040d64905f'
step_id: 'S20'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Investigate whether a categorical-conditional predicate (tipo_renta equals a literal implies a numeric casilla nonzero) can be evaluated without widening the Decimal-only casilla_values mapping that flows through every verification and calculation call site, decide between (a) a narrow operator extension scoped to the verification-evaluator boundary or (b) deferral, and record the decision plus its blocking constraints in the exec record

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Read the M210 inmobiliaria-branch silent-zero risk: `tipo_renta` (a `data_type = "text"` casilla) gates whether `base_imponible` should be non-zero, and every shipped `KNOWN_VERIFICATION_PREDICATE_OPERATORS` entry reads only `casilla_values: Mapping[CasillaId, Decimal]`, so the categorical antecedent cannot be expressed by `implies_nonzero`.
- Traced `_evaluate_advisory_predicate_fires` and `_evaluate_verification_predicates` (`src/aeat/application/modelo/_verification_actions.py`) and confirmed every existing call site passes exactly three positional arguments (expression, casilla_values, profile or expression/casilla_values), so any new parameter would have to be additive-optional to avoid a breaking signature change across the six shipped `test_verification_m*_advisory.py` suites and the M100/M200/M303 advisory tests.
- Found a parallel text-value channel already reaches the exact call site: `CalculationRevision.input_values_by_casilla_id: Mapping[CasillaId, str]` carries every operator-entered raw string independently of the Decimal `casilla_values` projection, and `_collect_revision_verification_findings` already holds `target.input_values_by_casilla_id` a few lines above its call into `_evaluate_verification_predicates`.
- Confirmed a working precedent for the same two-channel shape one layer over: `m210_resolve_base_imponible` (`src/aeat/domain/calculations/registry/_formula_runtime.py`) already threads a `text_values` parameter through `_EvalContext` without widening the Decimal `casilla_values` mapping the rest of the formula engine depends on.
- Identified the inmobiliaria-branch failure mode precisely via `_evaluate_m210_resolve_base_imponible`: every inmobiliaria input casilla is `required = false`, the formula raises when both `valor_catastral` and the acquisition/administrative substitute are absent, but a blank `dias_imputacion` with a valid `valor_catastral` and `coeficiente_imputacion_inmobiliaria` resolves a silent, formula-valid zero `base_imponible` with no validation error.
- Confirmed an asymmetric (ADVISORY-only, no `BLOCKING_RULE` branch) DSL operator already has precedent (`equals` is BLOCKING-only; `advisory_when_ratio_ge` is ADVISORY-only), and that mixed-shape arity validation (two casilla ids plus a literal) already has precedent in `roll_forward_balances`'s bespoke `_validate_surfaces.py` validator rather than the generic casilla-list validator.
- Decided outcome (a): a narrow, additive `casilla_equals_implies_nonzero` operator at the verification-evaluator boundary, reading the existing `target.input_values_by_casilla_id` channel through a new optional `text_values` parameter, with zero widening of the Decimal-only `casilla_values` contract anywhere else. Rejected widening `casilla_values` to a heterogeneous `Decimal | str` mapping (would force every other operator to defend against a non-Decimal value for one new operator) and rejected deferral (a feasible, narrowly-scoped, low-risk fix exists for the campaign's own highest-value finding).
- Recorded the full investigation, the rejected options, and the constraints in the companion ADR authored at the next Step.

## Outcome

Outcome (a) selected: implement a narrow `casilla_equals_implies_nonzero` operator at the verification-evaluator boundary via an additive-optional `text_values` parameter sourced from `target.input_values_by_casilla_id`. No widening of the Decimal-only `casilla_values` mapping anywhere in the formula engine, calculate path, or any other predicate operator.

## Notes

No incidents. This Step is investigation-and-decision only; no production code or registry file was modified. The decision and its full rationale are captured in the `2026-06-30-m210-categorical-conditional-predicate-adr`, authored at the immediately following Step.
