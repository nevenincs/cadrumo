---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S17'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Add a gate-behaviour test calling evaluate_verification_predicates directly for the M210 rendimientos-integros-to-base-imponible advisory, proving FIRES on positive-rendimientos-zero-base, HOLDS on positive-rendimientos-positive-base, and trivial-HOLD on zero-or-negative-rendimientos

## Scope

- `src/aeat/application/modelo/tests/test_verification_m210_advisory.py`

## Description

- Created `test_verification_m210_advisory.py` under `src/aeat/application/modelo/tests/`, mirroring the structure of the existing `test_verification_m131_advisory.py` reference test exactly: a module-level loader function that resolves the predicate off `resources().modelos.authority.validate_modelo("210").revisions["2025"]` by `predicate_id`, plus parametrized-style direct calls into `evaluate_verification_predicates`.
- Reused the shared `_workflow_profile()` fixture from `_verification_substance_support.py` rather than duplicating a `TaxpayerProfile`; the new predicate is a plain casilla-only `implies_nonzero` so profile content does not gate it.
- Built two new `CasillaId` constants (`rendimientos_integros`, `base_imponible`) via `validated_casilla_id` since these snake_case ids are not in the shared `_CASILLA_01`/etc. fixture set used by other M1xx tests.
- Wrote five tests: (1) confirms the pre-existing representante-fiscal BLOCKING_RULE predicate is preserved untouched alongside the new array entry; (2) confirms the new predicate's legal_refs cite `trlirnr-rdleg-5-2004:art-24`; (3) FIRES -- positive `rendimientos_integros` (5000.00) with zero `base_imponible` yields exactly one ADVISORY/WARNING finding carrying the art-24 legal ref; (4) HOLDS -- positive/positive yields no findings; (5) trivial-HOLD -- zero-antecedent, negative-antecedent, and entirely-absent casilla maps all yield no findings.
- Per no-tautological-calculation-tests, every assertion is against gate behaviour (finding count, kind, severity, legal_refs) produced by the real `evaluate_verification_predicates` evaluator and the real registry-loaded predicate, never a hand-computed Decimal expectation.
- Confirmed the file resolves under `tests-live-under-domain-tests-folders` (lives in the existing `src/aeat/application/modelo/tests/` package, no naked colocated test file).

## Outcome

`test_verification_m210_advisory.py` exercises the new ADVISORY guard's full behavioural contract (FIRES / HOLDS / trivial-HOLD) plus an explicit non-regression assertion that the pre-existing representante-fiscal BLOCKING_RULE predicate was not disturbed. All 5 tests pass; combined with the 13 tests in the S16 registry-shape file, 18 tests pass for this Phase.

## Notes

No incidents. The same two pre-existing, unrelated M100 failures noted in the S16 record were observed in the full registry-suite run; they are outside this Step's scope (this Step touches only `application/modelo/tests/`) and were not actioned.
