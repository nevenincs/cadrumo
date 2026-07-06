---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S03'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Refresh scale benchmark partition reporting

## Scope

- `src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`

## Description

- Search the benchmark and latency-budget vault records semantically before editing.
- Read the scale benchmark, repository partition implementation, aggregation entry point, and modelo transaction repository memoizer.
- Add real log-based partition reporting to the IVA quarterly and M130 calculate benchmark nodes.
- Add paired IVA P95 delta reporting between the short full-scan diagnostic and matching partitioned samples.
- Run the file-level ruff check and the changed integration benchmark nodes.

## Outcome

The scale benchmark now reports partition read counts and in-window row totals from the real transaction repository logs, without wrapping the repository or monkeypatching storage. The IVA benchmark also reports `paired_p95_delta_vs_full_scan` for the diagnostic sample pair. The changed benchmark nodes passed with real adapter output: IVA partitioned P95 `2.009s`, paired delta `6.072s`, `partition_reads=20`, `partition_in_window_rows=15000`; M130 calculate P95 `4.172s`, `partition_reads=4`, `partition_in_window_rows=7484`.

## Notes

Initial targeted pytest invocation was deselected by the project default `-m unit` addopts. Rerunning with `-m integration -n 0` collected and passed the changed benchmark nodes. The S03 code audit found no open findings.
