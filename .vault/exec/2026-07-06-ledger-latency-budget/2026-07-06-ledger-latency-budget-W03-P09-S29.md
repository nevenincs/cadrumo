---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S29'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Update impatriado out-of-window tests for one summary diagnostic

## Scope

- `src/aeat/application/aggregation/tests/test_impatriado_income_ledger.py`

## Description

- Attempt semantic grounding for impatriado summary test expectations; record the unavailable service and timed-out fallback.
- Update repository-backed impatriado tests to assert `out_of_window_summary` count and date span.
- Rename the wrong-direction repository-backed impatriado test so its name matches summary behavior.
- Keep pure full-catalogue impatriado issue assertions unchanged.

## Outcome
- `src/aeat/application/aggregation/tests/test_impatriado_income_ledger.py` now verifies that repository-backed partitioned impatriado aggregation emits one compact summary and zero row-level out-of-window issues.
- `uv run ruff check src/aeat/application/aggregation/tests/test_impatriado_income_ledger.py` passed.
- The three updated repository-backed impatriado tests passed.

## Notes

- `uv run vaultspec-rag search "impatriado income repository-backed out-of-window summary tests" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for the impatriado aggregation tests and summary fields.
