---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S27'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Update M130 and annual M100 income out-of-window tests for one summary diagnostic

## Scope

- `src/aeat/application/aggregation/tests/test_renta_income_aggregation.py and src/aeat/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py`

## Description

- Expand the S27 plan row to include annual M100 income tests discovered from the S22 repository-backed code path.
- Attempt semantic grounding for M130/M100 income summary test expectations; record the unavailable service and timed-out fallback.
- Update M130 repository-backed income tests to assert `out_of_window_summary` count and date span.
- Update annual M100 repository-backed income tests to assert the same summary contract.
- Keep pure full-catalogue income issue assertions unchanged.

## Outcome
- `src/aeat/application/aggregation/tests/test_renta_income_aggregation.py` now verifies compact summaries and zero row-level out-of-window issues for repository-backed M130 income partitions.
- `src/aeat/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py` now verifies compact summaries and zero row-level out-of-window issues for repository-backed M100 income partitions.
- `uv run ruff check src/aeat/application/aggregation/tests/test_renta_income_aggregation.py src/aeat/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py` passed.
- The five updated repository-backed income tests passed.

## Notes

- `uv run vaultspec-rag search "renta income M130 M100 repository-backed out-of-window summary tests" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for both income test files and the converted income aggregation path.
