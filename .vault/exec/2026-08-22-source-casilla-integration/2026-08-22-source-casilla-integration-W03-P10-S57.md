---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:9df15a0447f49fbaf7b10c6be8c1c0983446bd4b51b386305f8b7e786c517382'
step_id: 'S57'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
---

# determine whether asset amortization is a direct filing source or a duplicate of transaction-ledger expenses

## Scope

- `.vault/adr/2026-08-23-amortization-casilla-mapping-adr.md`

## Description

- Compare transaction-ledger expense authority with validated asset-schedule authority.
- Select the validated schedule as the exclusive activity-amortization source.
- Reject summation, silent precedence, and unvalidated scalar entries.
- Require exclusion or explicit collision refusal for overlapping transaction categories.

## Outcome

The accepted ADR makes a legally validated asset schedule authoritative for 2025 activity amortization at casillas 0208 and 0227. Competing transaction-ledger claims cannot contribute to the same filing fact.

## Notes

Implementation remains contingent on the complete legal schedule-validation surface defined by the ADR.
