---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:fe04e28c86a1382ffc28424ec66e2731d21a5cf3352b2f091ca20bd6d384cd34'
step_id: 'S185'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Refactor the size-budget subjects in formula_runtime.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/formula_runtime.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_formula_runtime_m131.py`
- `M` `src/cadrumo/domain/calculations/registry/formula_runtime.py`
- `A` `src/cadrumo/domain/calculations/registry/formula_runtime_m100.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_eo_agraria_indices_correctores.py`
- `M` `src/cadrumo/tests/test_decimal_enrollment_inventory.py`

## Notes

Source provenance is `adbdcc8875b9323b3ddc88a1984deea287380c6f`. Its immutable physical source comparison reduces `formula_runtime.py` from 1373 to 1035 lines and adds the 363-line Modelo 100 sibling, deletes the legacy in-module wrapper implementation, and makes the dispatcher directly import the canonical evaluator module. No source plan, size-budget baseline, or threshold changed.

Executor-reported focused receipts are: 8 EO tests in 28.96s; 18 Art. 85 plus arity tests in 45.16s; and 13 remediation-focused tests in 43.28s. The complete size audit exited 1 elsewhere but reported no `formula_runtime` offender; this is not a global green claim.

The combined 25/4 scanner result is non-green, unattributed, and excluded from acceptance. It is not represented as S185 verification evidence.
