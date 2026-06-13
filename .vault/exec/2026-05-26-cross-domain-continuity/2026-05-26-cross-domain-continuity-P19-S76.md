---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S76
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P19.S76 — M130 verificado-completo regression tests

## Outcome

Written two end-to-end regression tests in
`src/aeat/application/modelo/test_verificado_completo_regression.py` against
real encrypted SQLite storage and the real registry:

1. `test_verify_refuses_when_required_casillas_absent_m130` — calculates M130 with
   required casilla 02 (Gastos) absent; asserts `granted_verificado_completo is False`,
   `completeness_status is INCOMPLETE`, and findings contain `MISSING_REQUIRED_CASILLA`
   for each required casilla. The required casilla set is read dynamically from the
   registry to avoid hardcoding.

2. `test_verify_grants_when_required_casillas_supplied_m130` — calculates M130 with
   all required casillas (including 02) present; asserts `granted_verificado_completo is True`.

Also fixed `test_m130_all_zero_without_gastos_is_blocked` in
`test_verification_substance.py` (removed casilla 15 from casilla_inputs, added
`modelo-130-resultados-negativos-anteriores` binding) after discovering M130 casilla 15
is a `previous_filing`-bound casilla with no period anchors.

All 15 tests in the two files pass.

## Files changed

- `src/aeat/application/modelo/test_verificado_completo_regression.py` (new, S76 + S211)
- `src/aeat/application/modelo/test_verification_substance.py` (S76 regression fix)
