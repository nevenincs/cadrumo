---
tags:
  - '#exec'
  - '#m303-cross-period-carry-continuity'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-03-m303-cross-period-carry-continuity-plan]]'
  - '[[2026-06-03-m303-cross-period-carry-continuity-adr]]'
---

# `m303-cross-period-carry-continuity` `P03.S06` exec — author cross-period anti-regression test

## Action

Author `src/aeat/application/calculations/test_modelo_303_compensacion_carry_anti_regression.py` per ADR Phase 3.

## Result

Created the parametrised anti-regression module with four credit magnitudes (`baseline-42`, `credit-90`, `pure-credit-42`, `credit-150`). Each parametrisation drives the full 4T/N → 1T/N+1 carry through the real engine + real registry authority + real encrypted-SQLite observation repository. The load-bearing assertion compares two engine outputs (`carried_saldo == casilla_110`) at every magnitude; no hand-computed expectation participates.

The non-tautology contract is preserved: both sides of the equality are engine-produced, so the test fails the moment any structural change collapses the cross-period saldo magnitude (the exact regression hidden by commit `6e5a316a6` pre-`c2e05f644`).

```
src/aeat/application/calculations/test_modelo_303_compensacion_carry_anti_regression.py::test_carry_in_tracks_prior_period_saldo_magnitude[baseline-42] PASSED [ 25%]
src/aeat/application/calculations/test_modelo_303_compensacion_carry_anti_regression.py::test_carry_in_tracks_prior_period_saldo_magnitude[credit-90] PASSED [ 50%]
src/aeat/application/calculations/test_modelo_303_compensacion_carry_anti_regression.py::test_carry_in_tracks_prior_period_saldo_magnitude[pure-credit-42] PASSED [ 75%]
src/aeat/application/calculations/test_modelo_303_compensacion_carry_anti_regression.py::test_carry_in_tracks_prior_period_saldo_magnitude[credit-150] PASSED [100%]

4 passed in 83.69s
```

## M390 cross-cluster note

Per the plan's verification gate: the fix landed at the **test-fixture** layer in peer commit `c2e05f644`, not at the saldo formula or relation resolver. The M390 annual consolidation surface (which reads the same `iva.compensacion-disponible-fin-periodo` saldo) inherits **no change** to the saldo production path; no parallel M390 review is required. The follow-up flagged in task #248 (M390 annual aggregation for autoconsumo Art. 9.1.c LISIVA promotor) tracks a separate axis and is not gated by this campaign.
