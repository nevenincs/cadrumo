---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S12'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---




# build a multi-quarter M130 fixture (prior 1T/2T/3T filings with chosen ingresos/gastos including at least one quarter whose casilla 07 is negative and at least one non-zero casilla 16), let the engine produce each prior 07 and 16, and assert the 4T casilla 05 equals sum max(0,07_q) minus sum 16_q computed from the AEAT instrucciones rule via an independent helper, a different code path than the span binding under test, per no-tautological-calculation-tests

## Scope

- `src/aeat/application/calculations/tests/test_modelo_130_casilla_05_carry.py`

## Description

- Built `test_modelo_130_casilla_05_carry.py` with a multi-quarter fixture: prior 1T/2T/3T carrying chosen casilla 07 / 16 including a NEGATIVE prior 07 (contributing 0) and a NON-ZERO casilla 16.
- Asserted the 4T casilla 05 equals `Sum max(0, 07_q) - Sum 16_q` computed by an independent `_accumulation_identity` helper, a different code path than the span binding.

## Outcome

The accumulation-identity oracle (4T = 860 from 1T:+400/50, 2T:-150/0, 3T:+600/90) passes against real repositories. A raw-07 sum (710) or a dropped-minoración (1000) would fail loudly. Landed in commit `53de169cb`.

## Notes

Non-tautological per no-tautological-calculation-tests: the oracle is the verbatim AEAT identity applied to independently-fixed fixture inputs, asserted via a separate helper.
