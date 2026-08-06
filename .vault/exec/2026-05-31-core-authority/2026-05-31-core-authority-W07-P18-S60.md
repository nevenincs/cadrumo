---
tags:
  - '#exec'
  - '#core-authority'
step_id: S60
date: '2026-05-31'
modified: '2026-07-17'
body_hash: 'sha256:9c801524197e49674decfd12909b750a7190193953c9f8201291d89db7a8269d'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W07.P18.S60 - remove LedgerTransactionDirection alias in _renta_income_ledger

## Outcome

Removed `from ...domain.transactions import TransactionDirection as LedgerTransactionDirection`
alias from `application/aggregation/_renta_income_ledger.py`. Added `TransactionDirection`
to the existing import block. Replaced 1 alias reference.

## Commit

`d60e5241a` — refactor(aggregation): W07.P18.S60

## Files touched

- `src/aeat/application/aggregation/_renta_income_ledger.py` — alias removed, 1 reference updated

## Verification

51 passed (full aggregation ledger suite).
