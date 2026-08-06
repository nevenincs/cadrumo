---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:aa0c4d482d7960cff3e83bc30ada0968e5feb8b72e2c0122dcfa9fdf7b64db6d'
step_id: 'S13'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Run the M130 scale benchmark and record read, calculate, and annual residuals

## Scope

- `src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`

## Description

- Search the benchmark and latency-budget vault records for the M130 residual measurement requirement.
- Read the scale benchmark nodes for full ledger read, annual renta aggregation, and M130 calculate diagnostics.
- Run the selected integration benchmark nodes against the real 30k-row encrypted SQL fixture.
- Record the full-catalogue read, annual full-scan, and M130 calculate residuals after the batch-read adoption.

## Outcome

The selected scale benchmark nodes passed after pinning temp storage to the workspace drive. Post-batch-read measurements were:

- `ledger_read_diagnostic`: n=3, P95 `6.278s`, mean `6.115s`, min `5.819s`, max `6.278s`, out-of-scope full-catalogue read.
- `annual_renta_aggregation_diagnostic`: n=3, P95 `6.797s`, mean `6.435s`, min `6.157s`, max `6.797s`, out-of-scope pending invoice-date key.
- `modelo_calculate_diagnostic`: n=4, P95 `2.666s`, mean `2.036s`, min `1.634s`, max `2.666s`, `partition_reads=4`, `partition_in_window_rows=7484`.

## Notes

The first benchmark attempt failed during fixture seeding with SQLite `database or disk is full` because the default temp drive had about 78 MB free. Rerunning with `TEMP`, `TMP`, and `TMPDIR` pinned to `.tmp-bench` on the workspace drive passed: `3 passed in 136.97s`.

The RAG service/index remained degraded for this step. Code and vault semantic searches were attempted with fallback; the code fallback first hit a local Qdrant lock, then returned no benchmark-file results until a narrower query returned unrelated low-score hits. Direct reads of the current benchmark file supplied the executable grounding after the RAG attempts.
