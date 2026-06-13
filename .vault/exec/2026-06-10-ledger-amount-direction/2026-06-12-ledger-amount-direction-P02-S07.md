---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S07'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Provider Boundary Contract

## Scope

Step `P02.S07`.

## Description

- Updated the provider contract to return `ParsedLedgerRow(raw, direction)`.
- Consumed source-signed amounts once at the adapter boundary.
- Stored `abs(amount)` on the raw transaction and allowed the parsed-row contract to carry `INTERNAL_TRANSFER`.

## Outcome

All file-backed providers produce magnitude rows paired with explicit direction.

## Notes

No downstream source-format importer reads stored amount sign.
