---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S07'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---




# confirm casilla 07 formula (07 = 04 - 05 - 06) is unchanged and now reads a populated bound casilla 05, then verify casilla 05 no longer over-states the resultado on a cumulative 2T, 3T, and 4T calculate via a registry-load behaviour assertion

## Scope

- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/formulas/0001-formulas.toml`

## Description

- Confirmed the casilla 07 formula (`07 = 04 - 05 - 06`, `modelo-130-resultado-apartado-i`) is unchanged and now reads the populated bound casilla 05.
- Verified via registry-load behaviour assertions that casilla 05 no longer over-states the resultado on cumulative 2T/3T/4T and resolves to a clean absent-by-design zero at 1T.

## Outcome

Casilla 07 deducts the carried casilla 05 on cumulative quarters; the over-payment closes at the value level. `test_modelo_130_registry.py` (10 passed) and `test_committed_registry.py` green. Landed in commit `a67b77c87`.

## Notes

The registry tests assert casilla 05 against an independently-computed identity, a different code path than the binding, per no-tautological-calculation-tests.
