---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
step_id: 'S03'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Application Transaction Projections

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Require `created_at` and `modified_at` on `LedgerTransactionPayload`.
- Require `created_at` and `modified_at` on `LedgerTransactionReviewPayload`.
- Emit ISO strings directly from transaction timestamps in application projection builders.

## Outcome

Application read and review payloads expose non-null lifecycle timestamps for mutation, list, and review surfaces.

## Notes

Payload optionality was removed to match the no-legacy timestamp storage contract.