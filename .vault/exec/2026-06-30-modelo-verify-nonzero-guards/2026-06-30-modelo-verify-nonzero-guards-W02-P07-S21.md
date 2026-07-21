---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S21'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
  - "[[2026-06-30-m210-categorical-conditional-predicate-adr]]"
---

# Act on the prior Step's decision, authoring a companion ADR documenting the new casilla_equals_implies_nonzero operator's grammar, evaluator semantics, and registry-build validation coverage via vaultspec-adr when outcome (a) is selected, or scaffolding a follow-up research document recording the deferral and the casilla_values plumbing constraint via vaultspec-core vault add research when outcome (b) is selected

## Scope

- `.vault/adr/`

## Description

- Authored the companion ADR `2026-06-30-m210-categorical-conditional-predicate-adr` (status `accepted`) documenting outcome (a) from the prior Step.
- Recorded the Problem Statement: the M210 inmobiliaria branch is the campaign's highest-value silent-zero risk (the most common M210 filing scenario, a non-resident owning Spanish real estate with no rental income, still owes imputed-rent IRNR) but its trigger is a categorical equality on `tipo_renta`, not a numeric antecedent.
- Documented the Considerations: the base-imponible formula as formal authority, the precise silent failure mode (blank `dias_imputacion` against a populated `valor_catastral`/`coeficiente_imputacion_inmobiliaria`), the existing parallel text-value channel (`CalculationRevision.input_values_by_casilla_id`) already reaching the verification call site, the `m210_resolve_base_imponible` `text_values` precedent at the formula-engine layer, the existing ADVISORY-only operator asymmetry (`equals` / `advisory_when_ratio_ge`), and the `roll_forward_balances` bespoke-validator precedent for mixed casilla-id-plus-literal arity.
- Recorded the three Considered options: (a) narrow operator extension at the verification-evaluator boundary (chosen), (b) widen `casilla_values` to a heterogeneous `Decimal | str` mapping (rejected as a type-erasure boundary leak), (c) defer to a follow-up feature (rejected as contradicting the campaign's own no-silent-under-declaration discipline for a feasible, low-risk fix).
- Documented the Constraints: the operator is ADVISORY-only by convention with no enforced `finding_kind`-pairing validator (a known, accepted gap mirroring `equals`/`advisory_when_ratio_ge`); `text_values` is threaded as an additive optional keyword parameter to preserve every existing 3-positional-argument call site; the literal comparison is exact-string, no case/accent normalisation.
- Recorded the Implementation plan: register `casilla_equals_implies_nonzero` in `KNOWN_VERIFICATION_PREDICATE_OPERATORS`, document it in `VerificationPredicateDefinition`'s DSL docstring, add the evaluator branch in `_evaluate_advisory_predicate_fires`, thread `text_values` through `_evaluate_verification_predicates` and its public alias, pass `target.input_values_by_casilla_id` at the existing `_collect_revision_verification_findings` call site, add a bespoke registry-build arity/casilla-existence validator in `_validate_surfaces.py` mirroring `roll_forward_balances`, and append the M210 inmobiliaria predicate to the 2025 revision's `verification_expectations/0001-verification_predicates.toml` grounded in TRLIRNR art. 13.1.h and art. 24.
- Recorded Rationale, Consequences (gains, difficulties, pitfalls avoided), and a Codification candidates section explicitly concluding none is proposed -- the ADR extends established conventions (asymmetric operators, additive-optional parameters) already present in the DSL rather than introducing a new durable cross-session constraint.

## Outcome

`.vault/adr/2026-06-30-m210-categorical-conditional-predicate-adr.md` lands with status `accepted`, fully grounding the `casilla_equals_implies_nonzero` operator design, its evaluator semantics, its registry-build validation coverage, and the rejected alternatives, satisfying this Step's "when outcome (a) is selected" branch.

## Notes

No incidents. Outcome (b) (the deferral-research-stub branch) was not exercised since outcome (a) was selected at the prior Step.
