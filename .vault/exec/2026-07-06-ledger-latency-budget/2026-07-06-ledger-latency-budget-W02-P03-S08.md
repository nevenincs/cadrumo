---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Implement secure-object targeted batch load

## Scope

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py`

## Description

- Search the secure-object storage code and vault plan for the targeted batch-read requirement.
- Read the secure-object repository load, namespace scan, failure item, and row conversion paths before editing.
- Add `iter_many_with_failures` and `load_many` to `SecureObjectRepository`.
- Refactor namespace scans and targeted reads through one readable/unreadable raw-row conversion helper.
- Run storage ruff checks and existing readable/unreadable listing tests.
- Audit the change and record that no open findings remain.

## Outcome

`SecureObjectRepository` now supports targeted batch reads by namespace and natural object keys. `iter_many_with_failures` derives raw object-key digests, reads matching rows with one SQL `IN` query, and returns the established readable/unreadable item contract. `load_many` mirrors `list_records` by failing closed before yielding a partial readable subset if any selected row is unreadable.

## Notes

Direct batch parity tests are intentionally left to S09. For this implementation step, ruff passed and existing namespace listing tests passed after the shared conversion refactor.
