---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:2b2e3f3e7bdddfd1d63166ab6a6b82cf39331194efcaf8459466f2de4920fee1'
step_id: 'S02'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Manual Direction Policy

## Scope

Step `P01.S02`.

## Description

- Removed sign-to-direction coupling from `ManualLedgerTransactionCommand`.
- Kept zero-amount refusal and the `INTERNAL_TRANSFER` tax/evidence payload gate.
- Updated command tests to accept the same positive magnitude for incoming and outgoing rows.

## Outcome

Manual ledger creation now uses `direction` as the only flow authority.

## Notes

Negative manual amounts are refused as invalid magnitudes.
