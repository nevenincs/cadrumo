---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:9bd4bc0c95db76f0fc71a1697fa0864bbb5c50a2c24b7713b7093288e15ce36b'
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
