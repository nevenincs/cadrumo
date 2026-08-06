---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:a03896b969ab695b2ce7e935d872dd66b0b1ca742c614d550f3dace5b146c4b9'
step_id: 'S11'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Read secure_objects.py in full and identify a cohesive extraction boundary that shrinks it under its override, preserving the public API and behavior exactly

## Scope

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py`

## Description

- Read `secure_objects.py` in full (1312 lines against its 1295 override, 17 over).
- Identified `_list_item_from_raw_row` -- the raw-SQL-row to typed `SecureObjectListItem` fault-isolation decoder used by `iter_records_with_failures` -- as the cohesive extraction boundary, following the exact pattern the sibling `_secure_object_row_codec.py` module already established for `secure_object_record_from_row`.
- Confirmed `enforce_registered_row_schema` could be threaded as a `Callable` parameter to keep the moved decoder self-contained.

## Outcome

Extraction boundary confirmed: move `_list_item_from_raw_row` to `_secure_object_row_codec.py` as `secure_object_list_item_from_raw_row`.

## Notes

Landed by coder-perf (parallel P04 assignment per the plan's Parallelization section) as part of commit `93303b177`; this record documents the completed Step for plan-closure purposes per `plan-closure-requires-exec-records`.
