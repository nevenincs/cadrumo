---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S19'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Emit count and date-span summaries from indexed and fallback partitions

## Scope

- `src/aeat/adapters/persistence/profile/transactions.py and src/aeat/adapters/persistence/profile/tests/test_transaction_date_index.py`

## Description

- Attempt semantic search for repository partition summary emission.
- Read `partition_by_date_range`, the plan's summary phase, and current date-index partition tests before editing.
- Expand the S19 plan scope to include repository-level date-index tests.
- Emit `OutOfWindowTransactionSummary` from both complete-index and stale-index fallback partition paths.
- Keep row-level stubs temporarily for migration compatibility with existing aggregation consumers.
- Assert summary count and min/max filing dates in indexed, batch-read, parity, and stale-index fallback tests.
- Run ruff for touched repository/domain files and the focused partition tests.
- Audit the change and record that no open findings remain.

## Outcome

`TransactionCatalogueRepository.partition_by_date_range` now populates `out_of_window_summary` on both indexed and full-scan fallback partitions. The focused date-index tests prove count and date-span values while preserving the existing in-window and row-level fallback assertions during the consumer migration.

## Notes

The summary is additive in this step: row-level stubs remain populated so the aggregation adapters keep their current behavior until S20-S25 switch to summary diagnostics. Ruff passed for the touched repository/domain files, and the four focused partition tests passed.
