---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:41d136a5d5ce416af13838d93fb4fa95edb41a3e6e24ee3a755e442339a6c33e'
step_id: 'S21'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Convert IVA repository-backed aggregation to emit the out-of-window summary

## Scope

- `src/aeat/application/aggregation/_iva_ledger.py`

## Description

- Attempt semantic grounding for IVA repository-backed out-of-window diagnostics; record the unavailable service and timed-out fallback.
- Add `out_of_window_summary` to `IvaLedgerAggregation` for repository-backed date partitions.
- Populate the IVA repository-backed result from `LedgerDatePartition.out_of_window_summary`, deriving from stubs only for migration compatibility.
- Preserve full-catalogue row-level `OUTSIDE_PERIOD` issue emission for paths that intentionally load every transaction.

## Outcome
- `src/aeat/application/aggregation/_iva_ledger.py` now stops appending one IVA issue per out-of-window partition stub on the repository-backed date-window path.
- The repository-backed IVA smoke probe passed with one in-window observation, zero row-level issues, and a summary count/date span for the out-of-window row.
- `uv run ruff check src/aeat/application/aggregation/_iva_ledger.py` passed.
- `uv run pytest -q -n 0 src/aeat/application/aggregation/tests/test_iva_ledger.py::test_iva_aggregation_buckets_on_value_date_caja_basis_only` passed.

## Notes

- `uv run vaultspec-rag search "IVA ledger repository-backed aggregation out-of-window summary diagnostics source mesh" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for the affected IVA, source-mesh, and transaction-domain files.
- Two stale pytest node names were attempted before locating the current IVA test names; no tests ran for that mistaken invocation.
