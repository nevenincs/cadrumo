---
tags:
  - '#exec'
  - '#core-authority'
step_id: S59
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W07.P18.S59 - remove LedgerTransactionDirection alias in _renta_ledger

## Outcome

Removed `from ...domain.transactions import TransactionDirection as LedgerTransactionDirection`
alias import from `application/aggregation/_renta_ledger.py`. Merged `TransactionDirection`
into the existing `domain.transactions` import block. Replaced 3 alias references with
`TransactionDirection` directly.

## Commit

`827b57d8a` — refactor(aggregation): W07.P18.S59

## Files touched

- `src/aeat/application/aggregation/_renta_ledger.py` — alias removed, 3 references updated

## Verification

`uv run pytest src/aeat/application/aggregation/test_renta_ledger_helpers.py src/aeat/application/aggregation/test_renta_ledger.py -q` — 27 passed.
