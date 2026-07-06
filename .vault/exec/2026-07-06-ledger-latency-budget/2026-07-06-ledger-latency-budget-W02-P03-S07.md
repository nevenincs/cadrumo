---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S07'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Add secure-object batch outcome contract

## Scope

- `src/aeat/adapters/persistence/storage/sql/_secure_object_records.py`

## Description

- Search the storage code and vault records for the targeted secure-object batch-read contract.
- Read the existing secure-object records and namespace scan implementation before editing.
- Add a `SecureObjectBatchLoadItem` alias that reuses the established `SecureObjectRecord | SecureObjectUnreadable` outcome model.
- Run the records-module ruff check.
- Audit the change and record that no open findings remain.

## Outcome

The storage records module now names the batch-read item contract explicitly while preserving the same readable/unreadable failure surface used by namespace scans. S08 can implement targeted SQL reads without inventing a new diagnostics model or weakening unreadable-row reporting.

## Notes

No runtime behavior changed in this step. The records-module ruff gate passed, and the rolling audit found no issues.
