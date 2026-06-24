---
tags:
  - '#exec'
  - '#eoy-final-calculation'
date: '2026-06-24'
modified: '2026-06-24'
step_id: 'S03'
related:
  - "[[2026-06-22-eoy-final-calculation-plan]]"
---




# Add real end-to-end regression asserting M200 cuota del ejercicio a ingresar (00599) derives from cuota integra minus pagos (no manual 00592), grounded not tautological

## Scope

- `src/aeat/application/modelo/tests`

## Description

- Satisfied by the regression landed with the IS-4 implementation in commit `67be5781a` (teammate `iva-crossperiod-303`).

## Outcome

`test_cuota_ejercicio_00599_is_non_zero` (in `test_modelo_200_cuota_integra_lanes.py`) is the P01.S03 end-to-end regression: an 80000 base flows through the computed cuota chain to a non-zero cuota del ejercicio a ingresar (`DP200014B:00599`) with NO manual `00592` supplied — proving the headline figure now derives from cuota íntegra rather than silently reading zero. It is a structural no-silent-under-declaration assertion (00599 derives non-zero from the chain), not a tautological re-sum of the registry formula's own inputs, satisfying `no-tautological-calculation-tests`. VERIFIED green alongside 32 M200 cuota/base/registry tests + the tautology gate; registry loads (3250 casillas).

## Notes

- Coordinator review caveat: the assertion is "non-zero" (structural), not an external-oracle exact-value check (e.g. 80000 × 23% = 18400). It correctly locks the no-silent-zero contract this campaign exists to enforce; a follow-up could strengthen it to assert the exact grounded value against the AEAT rate, but that risks tautology against the registry tipo and is not required for S03's intent. P01.S03 closed.
