---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Pin date-index fallback parity

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_transactions_repository.py`

## Description

- Search the code and vault records for the O2 date-index completeness gate and fallback parity contracts.
- Read the transaction repository test module and the existing date-index-specific tests before editing.
- Add a repository-level test that compares a complete-index partition to a stale-index full-scan fallback partition.
- Run the file-level ruff check and the focused unit test.
- Audit the change and record that no open findings remain.

## Outcome

`test_transactions_repository.py` now has a real SQL-backed guard for the O2 fallback contract. The test saves a multi-period catalogue, captures the complete-index partition, deletes one derived date-index row, then asserts the fallback partition is served with `index_complete=False` while preserving the same in-window transactions and out-of-window projections. The focused unit test passed.

## Notes

The exec scaffold command created this record but failed while printing the post-create hint because of a Windows Rich console flush error. No file content was lost, and the created record was verified before editing.
