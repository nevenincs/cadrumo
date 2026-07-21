---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S26'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Update IVA out-of-window tests for one summary diagnostic

## Scope

- `src/aeat/application/aggregation/tests/test_iva_ledger.py`

## Description

- Attempt semantic grounding for IVA summary test expectations; record the unavailable service and timed-out fallback.
- Update repository-backed IVA out-of-window tests to assert `out_of_window_summary` count and date span.
- Rename the reviewed-excluded/archived repository-backed IVA test so its name matches summary behavior.
- Keep pure full-catalogue IVA issue assertions unchanged.

## Outcome
- `src/aeat/application/aggregation/tests/test_iva_ledger.py` now verifies that repository-backed partitioned IVA aggregation emits one compact summary and zero row-level out-of-window issues.
- `uv run ruff check src/aeat/application/aggregation/tests/test_iva_ledger.py` passed.
- The three updated repository-backed IVA tests passed.

## Notes

- `uv run vaultspec-rag search "IVA ledger tests out-of-window summary repository-backed diagnostics" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for the IVA aggregation tests and summary fields.
