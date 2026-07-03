---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-30'
step_id: 'S04'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-code-reviewer: VERIFICATION GATE 5a - run full-calc, cross-period-continuity, and oracle suites after the relation-op typing and assert NO casilla value shifts and binding-aggregation-is-typed conformance green

## Scope

- `src/aeat/domain/calculations/registry/tests/test_modelo_303_registry.py`

## Description

- Verification gate 5a: run the full-calc, cross-period-continuity, and oracle suites after the relation-op typing and assert NO casilla value shifts plus binding-aggregation-is-typed conformance green.
- Update `test_modelo_390_registry` to assert the typed op via `relation_aggregation_op` against the enum members instead of the prior dict shape.

## Outcome

- The full registry plus calculations plus core suites passed (3664 tests), unchanged baseline; the #1 refunded-period, #7/#12 M390 FIFO, pull-vs-calculate parity, cross-period clean-state, M180/190/193, and test_binding_aggregation gates passed; collect-only clean; ruff clean. No casilla value shifted.

## Notes

- One test (`test_modelo_390_declares_annual_compensation_result_fields`) asserted the old `{"op": ...}` dict shape and was migrated to the typed-member assertion via the accessor, per the rule that tests assert against enum members.
