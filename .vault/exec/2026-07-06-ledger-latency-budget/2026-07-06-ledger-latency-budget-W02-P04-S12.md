---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:5fe4c90a2c41a0102703cae88457cea18222414b099d9b6ff475969127c6a61f'
step_id: 'S12'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Prove targeted partition reads use one storage batch while preserving in-window and out-of-window sets

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_transaction_date_index.py`

## Description

- Search the date-index tests and vault records for the partition batch-read proof requirement.
- Read the existing partition split, parity, and stale-index tests plus the secure-object batch SQL instrumentation pattern.
- Add a real SQLAlchemy statement observer around `partition_by_date_range`.
- Assert the complete-index partition preserves the expected in-window transactions and out-of-window stubs.
- Assert the read emits one targeted secure-object `object_key IN` batch query and only one point secure-object lookup for the membership index.
- Run the date-index test ruff check, the new focused test, and the neighboring partition tests.
- Audit the change and record that no open findings remain.

## Outcome

`test_transaction_date_index.py` now proves the transaction partition adoption at the repository boundary. The new test saves two in-window and two out-of-window rows, observes the real SQL emitted by `partition_by_date_range`, verifies the returned split, and confirms the secure-object path is one targeted batch read rather than one point lookup per in-window row.

## Notes

Ruff passed for the date-index test file, the focused batch-read proof passed, and the neighboring partition tests passed. A manual `vaultspec-rag index --type all --allow-fallback` refresh was attempted after S11 because the service returned stale snippets; the vault refresh failed with `not enough disk space` and the jobs view later reported the service was not running, so S12 used the already-captured semantic search hits plus direct current-file reads.
