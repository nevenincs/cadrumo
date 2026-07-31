---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:c51eada14640fb589ff3e96122ae9e83d19981c05e6a7ffe3c3d6f327fc17833'
step_id: 'S22'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
  - "[[2026-06-30-m210-categorical-conditional-predicate-adr]]"
---

# When outcome (a) was selected, implement the casilla_equals_implies_nonzero operator end to end -- the KNOWN_VERIFICATION_PREDICATE_OPERATORS entry, the regex and evaluator branch, and the registry-build validator coverage -- with a generic operator-level unit test in the same commit, otherwise close this Step immediately with a one-line exec record cross-referencing the deferral

## Scope

- `src/aeat/domain/calculations/registry/_schema.py`

## Description

- Added `casilla_equals_implies_nonzero` to `KNOWN_VERIFICATION_PREDICATE_OPERATORS` in `src/aeat/domain/calculations/registry/_schema.py`, with an inline comment documenting its grammar (`casilla_equals_implies_nonzero(["antecedent_casilla_id", "literal", "consequent_casilla_id"])`), its ADVISORY-only status, and the asymmetry it mirrors (`equals` BLOCKING-only, `advisory_when_ratio_ge` ADVISORY-only).
- Extended `VerificationPredicateDefinition`'s DSL docstring with the operator's full semantics: FIRES iff the antecedent TEXT casilla's operator-entered raw value equals the literal AND the consequent (Decimal) casilla is zero; a missing or differing antecedent holds trivially (no advisory), the same convention as the numeric-antecedent operators.
- Added `_PREDICATE_CASILLA_EQUALS_IMPLIES_NONZERO` regex and `_parse_predicate_raw_tokens` helper in `src/aeat/application/modelo/_verification_actions.py` (the raw-token parser does not validate tokens as casilla ids up front, since the middle token is a literal string, unlike `_parse_predicate_casilla_ids`).
- Added the evaluator branch in `_evaluate_advisory_predicate_fires`: parses exactly three tokens (returns False on bad arity), validates the antecedent and consequent tokens as canonical casilla ids via `_validated_predicate_casilla_id`, then fires iff `text_values.get(antecedent_id) == literal` and `casilla_values.get(consequent_id, Decimal(0)) == Decimal(0)`.
- Threaded a new additive-optional `text_values: Mapping[CasillaId, str] = MappingProxyType({})` parameter onto `_evaluate_advisory_predicate_fires` and `_evaluate_verification_predicates` (and their public aliases), preserving every existing 3-positional-argument call site across the six shipped `test_verification_m*_advisory.py` suites and the M100/M200/M303 advisory tests.
- Wired `target.input_values_by_casilla_id` as the `text_values` argument at the existing Layer-2 predicate-gate call site inside `_collect_revision_verification_findings`.
- Added the bespoke registry-build validator `_casilla_equals_implies_nonzero_predicate_failures` in `src/aeat/domain/calculations/registry/_validate_surfaces.py` (mirroring `roll_forward_balances`'s shape rather than the generic `_casilla_list_predicate_failures`, since the middle token is a literal, not a casilla id): rejects a malformed arity, an unmatched expression, an unknown antecedent or consequent casilla id, or an empty literal, all at registry load rather than letting the runtime evaluator's defensive bad-arity branch silently mask a typo. Wired into `validate_verification_expectation_section`'s `op_name` dispatch.
- Added the generic operator-level unit tests in `src/aeat/application/modelo/tests/test_verification_substance.py`: a parametrized `test_casilla_equals_implies_nonzero_fires_cases` covering antecedent-matches/consequent-zero (fires), antecedent-matches/consequent-nonzero (holds), antecedent-differs (holds), and antecedent-absent (holds); plus standalone tests for the default-empty `text_values` behaviour, bad-arity defensive non-firing, the ADVISORY-only (no `BLOCKING_RULE` branch, trivially holds via the unmatched-expression default) property, and the full `evaluate_verification_predicates` entry point threading `text_values` end to end into a real `ModeloVerificationFinding`.
- Added `casilla_equals_implies_nonzero` to the exhaustive operator-coverage probe in `test_verification_substance_workflow.py`'s `test_runtime_evaluator_recognises_every_known_predicate_operator`, confirming every member of `KNOWN_VERIFICATION_PREDICATE_OPERATORS` has both a probe expression and a regex attribute under test.

## Outcome

The `casilla_equals_implies_nonzero` operator is implemented end to end: schema registration, evaluator branch, registry-build validator, and a generic operator-level test suite, all landing together. The operator is now available to any future predicate gated on a categorical (text) casilla equality, not only M210.

## Notes

No incidents. Outcome (a) was selected at `S20`/`S21`, so the "otherwise close this Step immediately" deferral branch was not exercised.
