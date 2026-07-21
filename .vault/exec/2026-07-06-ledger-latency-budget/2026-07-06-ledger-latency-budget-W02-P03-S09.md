---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S09'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Prove secure-object batch load parity

## Scope

- `src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part3.py`

## Description

- Search storage tests and vault records for the secure-object batch-load parity requirement.
- Read the part3 secure-object test module and existing unreadable-row patterns before editing.
- Add a readable-row parity test comparing `load_many` to repeated `load` calls and asserting one targeted SQL `IN` query.
- Add a mixed readable/schema-drift test covering `iter_many_with_failures` and fail-closed `load_many`.
- Run storage ruff checks and the two focused batch-load tests.
- Audit the change and record that no open findings remain.

## Outcome

`test_secure_objects_part3.py` now proves the new batch primitive against real encrypted SQLite storage. The readable test confirms missing keys are omitted, non-requested rows are not returned, loaded payloads match repeated single loads, and the repository emits exactly one targeted `object_key IN` select. The failure test confirms schema drift remains visible as a typed unreadable outcome and that fail-closed `load_many` raises before yielding a partial subset.

## Notes

The focused ruff and unit test gates passed, and the rolling audit found no issues.
