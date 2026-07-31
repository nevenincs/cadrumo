---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:980d8f3ab777471c657e8c92453fb67883e973d0d8c6866e77f662d2cd1dc66e'
step_id: 'S28'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Update M130 gasto out-of-window tests for one summary diagnostic

## Scope

- `src/aeat/application/aggregation/tests/test_renta_gasto_aggregation.py`

## Description

- Attempt semantic grounding for M130 gasto summary test expectations; record the unavailable service and timed-out fallback.
- Update repository-backed gasto tests to assert `out_of_window_summary` count and date span.
- Rename the wrong-direction repository-backed gasto test so its name matches summary behavior.
- Keep pure full-catalogue gasto issue assertions unchanged.

## Outcome
- `src/aeat/application/aggregation/tests/test_renta_gasto_aggregation.py` now verifies that repository-backed partitioned gasto aggregation emits one compact summary and zero row-level out-of-window issues.
- `uv run ruff check src/aeat/application/aggregation/tests/test_renta_gasto_aggregation.py` passed.
- The three updated repository-backed gasto tests passed.

## Notes

- `uv run vaultspec-rag search "renta gasto M130 repository-backed out-of-window summary tests" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for the gasto aggregation tests and summary fields.
