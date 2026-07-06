---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S14'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Update the code reference with paired before and after batch-read measurements

## Scope

- `.vault/reference/2026-07-06-ledger-perf-optimization-reference.md`

## Description

- Search the latency-budget vault records for the batch-read measurement update requirement.
- Read the reference document and the S13 benchmark execution record before editing.
- Append a dated W02 batch-read measurement update to the reference.
- Record the S03 pre-batch M130 baseline, the S13 post-batch M130 measurement, and the full-scan residual diagnostics.
- Note the temp-drive disk-space condition that affected the first S13 benchmark attempt.

## Outcome

The reference now records the concrete batch-read before/after: M130 calculate P95 moved from the S03 pre-batch `4.172s` baseline to the S13 post-batch `2.666s` measurement, a `1.506s` / `36.1%` P95 reduction while keeping `partition_reads=4` and `partition_in_window_rows=7484`. It also records the S13 full-scan residuals: ledger read P95 `6.278s` and annual renta P95 `6.797s`.

## Notes

The RAG fallback for this step returned no matching vault documents because the local index remained degraded after the service disk-space failure. The edit was grounded by direct reads of the current reference and S13 execution record.
