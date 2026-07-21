---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S40'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Add a 30k-row single-transaction mutation benchmark to expose save-side residuals

## Scope

- `src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`

## Description

- Re-ground the write-path residual through semantic code and vault search.
- Read the transaction repository `_reconcile` and `_serialise_transaction` path plus the existing scale benchmark structure.
- Add a real 30k-row single-transaction save benchmark to `test_ledger_scale_benchmark.py`.
- Report namespace payload-hash scan timing, all-row serialize+hash timing, and real one-row save timing.
- Restore the original seeded catalogue after the mutation benchmark to avoid polluting later benchmark nodes.
- Run ruff and the focused integration benchmark node.

## Outcome
- `test_single_transaction_save_reports_write_path_latency` now exposes the save-side residual on the real encrypted SQLite scale fixture.
- `uv run ruff check src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py` passed.
- `uv run pytest -q -n 0 -m integration src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py::test_single_transaction_save_reports_write_path_latency -s` passed: 1 passed in 74.61s.
- First S40 measurements: namespace hash scan P95 `0.201s`, serialize+hash all 30k rows P95 `1.399s`, single-transaction save P95 `2.659s`.

## Notes

- Semantic code search returned `src/aeat/adapters/persistence/profile/transactions.py`, especially the per-row storage and serialization paths. Semantic vault search returned the W05 plan rows and research finding F6.
- The benchmark calls the repository's existing `_serialise_transaction` method only to time the exact serialize+hash component already used by `_reconcile`; the real save timing still uses public `repo.save`.
- The benchmark run used the workspace `.tmp-bench` directory to avoid default temp-drive space limits.
