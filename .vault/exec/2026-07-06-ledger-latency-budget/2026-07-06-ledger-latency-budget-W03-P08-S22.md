---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:d6593720b5e8f2d0cc90d02fec84f8b132f8749ddf030d2cbd1284a707dee2c7'
step_id: 'S22'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Convert M130 income aggregation to emit the out-of-window summary

## Scope

- `src/aeat/application/aggregation/_renta_income_ledger.py`

## Description

- Attempt semantic grounding for M130 income repository-backed out-of-window diagnostics; record the unavailable service and timed-out fallback.
- Add `out_of_window_summary` to `RentaIncomeLedgerAggregation`.
- Populate the M130 quarterly repository-backed result from `LedgerDatePartition.out_of_window_summary`, deriving from stubs only for migration compatibility.
- Populate the annual M100 income repository-backed result from the same partition summary contract.
- Preserve full-catalogue row-level `OUTSIDE_PERIOD` issue emission for pure income aggregation paths.

## Outcome
- `src/aeat/application/aggregation/_renta_income_ledger.py` now stops appending one income issue per out-of-window partition stub on repository-backed paths.
- The M130 repository-backed smoke probe passed with one in-window observation, zero row-level issues, and one summary count/date span.
- The M100 income repository-backed smoke probe passed with the same summary behavior.
- `uv run ruff check src/aeat/application/aggregation/_renta_income_ledger.py` passed.
- `uv run pytest -q -n 0 src/aeat/application/aggregation/tests/test_renta_income_aggregation.py::test_q1_window_includes_jan_mar_transactions` passed.

## Notes

- `uv run vaultspec-rag search "M130 renta income repository-backed aggregation out-of-window summary diagnostics" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for the affected income, source-mesh, and transaction-domain files.
- Ruff applied an import-order fix after adding the summary model import.
- The first M130 smoke probe attempted to import `aggregate_renta_income_ledger_from_repositories` from the package facade, which does not export it; the rerun used the module import and passed.
