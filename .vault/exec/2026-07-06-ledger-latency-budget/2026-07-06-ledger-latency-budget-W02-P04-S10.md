---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Replace load-for-date-range per-id secure-object reads with the batch primitive

## Scope

- `src/aeat/adapters/persistence/profile/transactions.py`

## Description

- Search the transaction repository and vault records for the indexed date-range N+1 read.
- Read `load_for_date_range`, `partition_by_date_range`, the secure-object batch contract, and the selected-row failure surface before editing.
- Add a private transaction-row batch helper that maps selected transaction ids to secure-object digests and preserves missing-row omission.
- Route `load_for_date_range` through the batch helper while keeping the stale-index full-scan fallback unchanged.
- Run the repository ruff check and the focused date-range tests.
- Audit the change and record that no open findings remain.

## Outcome

`load_for_date_range` now decrypts candidate rows through one targeted secure-object batch read instead of one secure-object `load` call per candidate id. The helper preserves deterministic transaction-id ordering, omits missing encrypted rows the same way repeated single loads did, and keeps pydantic schema drift wrapped as `StoredTransactionDriftError`.

## Notes

`partition_by_date_range` still uses the old per-id loop until S11. Ruff passed for `transactions.py`, and the three focused `load_for_date_range` date-index tests passed.
