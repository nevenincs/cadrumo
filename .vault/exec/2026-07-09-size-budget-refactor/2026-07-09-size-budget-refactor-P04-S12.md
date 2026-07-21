---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S12'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Extract the identified cohesive chunk into a sibling module and re-wire callers, preserving the public API and behavior exactly

## Scope

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- `src/aeat/adapters/persistence/storage/sql/_secure_object_row_codec.py`

## Description

- Moved `_list_item_from_raw_row` to `_secure_object_row_codec.py` as `secure_object_list_item_from_raw_row`, threading `enforce_registered_row_schema` through as a `Callable` parameter to keep the codec module self-contained.
- Re-wired `secure_objects.py`'s `iter_records_with_failures` to call the relocated decoder.
- Removed the now-stale `iter_records_with_failures` callable-size override (182) from `test_codebase_size_budgets.py`: that method was unchanged by this extraction and is 82 lines, always under the 180 default, so the override had gone stale.
- Landed as commit `93303b177` ("refactor(storage): extract row-decode codec from secure_objects.py (#166)"): 3 files changed, 161 insertions, 134 deletions.

## Outcome

`secure_objects.py` shrank from 1312 to 1193 lines (override 1295). Public API and behavior unchanged.

## Notes

Landed by coder-perf (parallel P04 assignment per the plan's Parallelization section); this record documents the completed Step for plan-closure purposes per `plan-closure-requires-exec-records`.
