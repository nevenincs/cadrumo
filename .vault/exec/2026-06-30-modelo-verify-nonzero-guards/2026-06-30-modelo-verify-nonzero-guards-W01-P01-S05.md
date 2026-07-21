---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S05'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Add a gate-behaviour test calling evaluate_verification_predicates directly for the M202 04-to-13 advisory across all three revisions, proving FIRES on positive-04-zero-13, HOLDS on positive-04-positive-13, and trivial-HOLD on zero-or-negative-04

## Scope

- `src/aeat/application/modelo/tests/test_verification_m202_advisory.py`

## Description

- Create `test_verification_m202_advisory.py` mirroring the `test_verification_m131_advisory.py` template: load the predicate per revision via `resources().modelos.authority.validate_modelo("202")` (not a private cross-package test import, per `aeat-quality-gates` structural discipline), then call `evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())` directly.
- Parametrize across all three M202 revisions and assert: FIRES (one ADVISORY/WARNING finding) on positive `04` / zero `13`; HOLDS (no finding) on positive `04` / positive `13`; trivial-HOLD (no finding) on zero or negative `04` with zero `13`, including the absent-casilla-values case.

## Outcome

`test_verification_m202_advisory.py` ships with four parametrized test functions (ships-in-every-revision, fires, silent-when-present, silent-when-no-resultado) covering all three revisions. Ran together with S04's registry-shape suite: `pytest src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py src/aeat/application/modelo/tests/test_verification_m202_advisory.py -q` -> `20 passed`. `ruff check` clean on both new/modified test files. `pytest --collect-only -q` over `src/aeat/domain/calculations/registry` and `src/aeat/application/modelo` collects cleanly (4336 tests).

## Notes

No incidents. Every assertion is gate-behaviour (FIRES/HOLDS/trivial-HOLD), not a hand-computed Decimal oracle, per `no-tautological-calculation-tests`.
