---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:4272351998e9a7569b3ca28644b607d49d4e4725225f82924eb314d1d5b7be0b'
step_id: 'S20'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# classify amortization as the mandatory second adjudication candidate

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`

## Description

- Add the encrypted asset-amortization ledger as the mandatory second adjudication candidate after inventory.
- Keep it separate from the general asset register and the finca annual amortization computation.
- Require official adjudication of source independence, grain, destination, basis, rate, proration, caps, sign, rounding, absence, and overrides.

## Outcome

Amortization is now the second ordered census entry and cannot be silently folded into inventory, assets, fincas, or transaction expenses. Its follow-up must either authorize an exact bounded connection or record a governed non-connection outcome.

## Notes

The bundled strict loader passed and proved the manifest order is inventory first, asset amortization second. Both remain `connect_candidate`; no lexical amortization match is treated as tax authority.
