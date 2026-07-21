---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S24'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Convert impatriado income aggregation to emit the out-of-window summary

## Scope

- `src/aeat/application/aggregation/_impatriado_income_ledger.py`

## Description

- Attempt semantic grounding for impatriado repository-backed out-of-window diagnostics; record the unavailable service and timed-out fallback.
- Add `out_of_window_summary` to `ImpatriadoIncomeLedgerAggregation`.
- Populate the annual impatriado repository-backed result from `LedgerDatePartition.out_of_window_summary`, deriving from stubs only for migration compatibility.
- Preserve full-catalogue row-level `OUTSIDE_PERIOD` issue emission for pure impatriado aggregation.

## Outcome
- `src/aeat/application/aggregation/_impatriado_income_ledger.py` now stops appending one impatriado issue per out-of-window partition stub on the repository-backed path.
- The repository-backed impatriado smoke probe passed with one in-window observation, zero row-level issues, and one summary count/date span.
- `uv run ruff check src/aeat/application/aggregation/_impatriado_income_ledger.py` passed.
- `uv run pytest -q -n 0 src/aeat/application/aggregation/tests/test_impatriado_income_ledger.py::test_es_source_income_folds_into_impatriado_base` passed.

## Notes

- `uv run vaultspec-rag search "impatriado income repository-backed aggregation out-of-window summary diagnostics" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for the affected impatriado, source-mesh, and transaction-domain files.
- Ruff applied an import-order fix after adding the summary model import.
