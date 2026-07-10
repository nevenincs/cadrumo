---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S82'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write the M720 threshold-continuity E2E test asserting the prior-year asset baseline drives the re-declaration obligation across two renta years via real adapters (vaultspec-high-executor)

## Scope

- `src/aeat/application/calculations/test_modelo_720_baseline_continuity.py`

## Description

- Extend the existing Modelo 720 two-year fidelity test to resolve the committed prior-year bindings through `resolve_bindings_from_local_store`.
- Persist year N through the real `CalculationObservationRepository`, reload the year N baseline for the year N+1 context, and feed that resolved baseline into the re-declaration advisory helper.
- Assert the grown and omitted cuentas block produces one grounded advisory, while declared or below-threshold blocks stay silent.
- Add the negative guard that a missing `inmuebles.valoracion` source casilla raises instead of being silently defaulted.

## Outcome

- Satisfied in `src/aeat/application/calculations/tests/test_modelo_720_prior_year_baseline_fidelity.py`; the plan's historical non-tests path is stale.
- The test uses real repository storage and registry snapshots, with no fakes, mocks, monkeypatches, skips, or xfails.

## Notes

- The test proves explicit-zero carry semantics, not absent-category zero invention.
- Verified by the final scoped M720/M721 run, which passed 90 targeted tests after review fixes.
