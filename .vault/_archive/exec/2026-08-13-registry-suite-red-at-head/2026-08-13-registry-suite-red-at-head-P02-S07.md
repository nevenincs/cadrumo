---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:997a0fc80b8adda947c580bc72f1506bc81ec518c0e1813dfb3620943e912cde'
step_id: 'S07'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

# Sweep the IvaLedgerSelector fixtures for the two required axes and confirm each pytest.raises case still fires its originally asserted refusal rather than loosening the match

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Re-census every surviving `_IvaLedgerSelector` constructor and validation path.
- Confirm positive paths declare cash-accounting treatment and observation-role
  axes and retain the deliberate missing-role refusal probe.
- Run the focused reachability and aggregation-binding suites sequentially.

## Outcome

The old fixture population has been replaced by four live construction paths.
All three positive paths declare both axes. The fourth intentionally omits
`observation_roles` and still raises the exact validation refusal.

## Notes

- `test_binding_reachability_probe.py`: 4 passed.
- `test_ledger_iva_aggregation_binding.py`: 27 passed.
- Existing refusal matches remain `observation_roles`, `malformed`,
  `aggregation op 'sum'`, `not a ledger_iva_aggregation`, and
  `exemption_articles`; no assertion was loosened.
