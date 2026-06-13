---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S13'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---




# add the first-quarter-fires-nothing case: assert a 1T (and a first-filer/alta first quarter) produces casilla 05 = Decimal zero with absent-by-design provenance and emits no blocker and no prior-payment advisory

## Scope

- `src/aeat/application/calculations/tests/test_modelo_130_casilla_05_carry.py`

## Description

- Added `test_first_quarter_carry_resolves_nothing`: a 1T target resolves no casilla-05 carry (empty span), so the engine materialises absent-by-design zero with no prior.
- Added `test_first_filer_2t_alta_clean_state_suppresses_pre_activity_casilla_05_requirement`: a mid-year-alta (2T) first filer pre-activity 1T requirement is suppressed via the activity-start scoping, yielding a clean cross-period verdict with no blocker.

## Outcome

A 1T and a first-filer/alta first quarter produce casilla 05 = zero, no blocker, no advisory. Landed in commit `53de169cb`.

## Notes

The first-filer case asserts `verdict.clean` and that the casilla-05 binding id appears among the suppressed pre-activity dependencies, binding directly to the landed first-filer axis.
