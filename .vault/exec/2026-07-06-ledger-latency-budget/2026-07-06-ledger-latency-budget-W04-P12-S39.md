---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S39'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Run the scale benchmark and record validator delta in the reference

## Scope

- `src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`

## Description

- Re-ground the scale benchmark and prior latency measurements through semantic code and vault search.
- Read the benchmark file, S13 execution record, and reference measurement section before running S39.
- Run the selected 30k-row integration benchmark nodes with `TEMP`, `TMP`, and `TMPDIR` pinned to `.tmp-bench`.
- Append the post-validator benchmark measurements and S13 deltas to the reference.

## Outcome
- The selected scale benchmark nodes passed: `3 passed in 96.90s`.
- `ledger_read_diagnostic`: n=3, P95 `5.126s`, mean `4.969s`, min `4.691s`, max `5.126s`.
- `annual_renta_aggregation_diagnostic`: n=3, P95 `5.751s`, mean `5.379s`, min `5.144s`, max `5.751s`.
- `modelo_calculate_diagnostic`: n=4, P95 `1.141s`, mean `0.961s`, min `0.835s`, max `1.141s`, `partition_reads=4`, `partition_in_window_rows=7484`.
- `.vault/reference/2026-07-06-ledger-perf-optimization-reference.md` now records the post-validator deltas against S13: ledger read `-1.152s`, annual renta `-1.046s`, and M130 calculate `-1.525s` P95.

## Notes

- Semantic code search returned `src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`. Semantic vault search returned the active S39 plan row, the reference document, and the S13/S14 benchmark records.
- The benchmark run used the workspace `.tmp-bench` directory to avoid the default temp-drive space issue observed in S13.
