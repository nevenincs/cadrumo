---
tags:
  - '#exec'
  - '#core-authority'
step_id: S61
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W07.P18.S61 - remove LedgerTransactionDirection alias in _iva_ledger

## Outcome

Removed two-line alias import block from `application/aggregation/_iva_ledger.py`.
Merged `TransactionDirection` into the existing single `domain.transactions` import block.
Replaced 3 alias references with `TransactionDirection` directly.

## Commit

`d230fe18a` — refactor(aggregation): W07.P18.S61

## Files touched

- `src/aeat/application/aggregation/_iva_ledger.py` — alias removed, 3 references updated

## Verification

51 passed (aggregation suite includes iva_ledger tests).
