---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S11'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Replace partition-by-date-range per-id secure-object reads with the batch primitive

## Scope

- `src/aeat/adapters/persistence/profile/transactions.py`

## Description

- Search the transaction repository and vault records for the partition N+1 read.
- Read `partition_by_date_range`, the S10 batch helper, and the accepted completeness-gate constraints before editing.
- Route the complete-index in-window partition read through `_load_transactions_by_ids`.
- Preserve the stale-index full-scan fallback and plaintext out-of-window stub construction unchanged.
- Run the repository ruff check and focused partition/fallback tests.
- Audit the change and record that no open findings remain.

## Outcome

`partition_by_date_range` now decrypts the in-window transaction ids through the same targeted secure-object batch helper used by `load_for_date_range`. The completeness gate still compares the date-index id set against the encrypted membership index before trusting plaintext routing, and the fallback path still performs a full encrypted load when the index is stale.

## Notes

S12 remains responsible for proving the exact one-batch SQL shape at the repository-test layer. Ruff passed for `transactions.py`, and the three focused date-index partition tests plus the repository fallback parity test passed.
