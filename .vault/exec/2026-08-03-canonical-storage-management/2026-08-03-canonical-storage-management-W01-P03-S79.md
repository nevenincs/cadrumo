---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:14dae5f1cdc06303d0feb6c5a48e1a4e3c11dee976263c6c47f7fa685d436aab'
step_id: 'S79'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Fix bucket_scoped_storage_path's resolution of KEYSTORE_RELATIVE members, which places them nested under buckets/<bucket_id>/keystore/ and contradicts validate_keystore_separation's requirement that a bucket's keystore live at keystore/<bucket_id>/ as a sibling of buckets/, a live defect blocking S20 and S21

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py`

## Description

- Fix `bucket_scoped_storage_path`'s resolution of `KEYSTORE_RELATIVE` members, which placed them nested under `buckets/<bucket_id>/keystore/` and contradicted `validate_keystore_separation`'s requirement that a bucket's keystore live at `keystore/<bucket_id>/` as a sibling of `buckets/`.

## Outcome

Landed in commit `86b02bf68e` ("anchor the keystore at the storage root, not under buckets/"), committed at HEAD. Adds `StorageScope.KEYSTORE_ROOT` distinct from `KEYSTORE_RELATIVE`: `KEYSTORE_ROOT` anchors the keystore directory itself at `<root>/keystore/<bucket_id>/`, sibling to `buckets/`; `KEYSTORE_RELATIVE` now names only what nests beneath that anchor. `test_the_scoped_accessor_resolves_bucket_and_keystore_members` was rewritten to assert the sibling shape, with its own docstring recording that an earlier version of the same assertion pinned the wrong nested shape and was itself the bug. A companion test binds the accessor's output directly to the real `validate_keystore_separation` rather than a hand-pinned literal, and a positive control feeds the validator a nested path to confirm it still refuses. ADR amended (R13 corrected, R23 added recording the defect and its closure).

## Notes

This fix landed mid-session while the ADR audit was underway — R23 was originally written recording the defect as unfixed, uncommitted peer WIP; the fix committed before that ADR content was even reported. Caught on a second independent verification pass and both the plan and ADR were corrected within the hour. S20 and S21 (re-pointing `bucket_paths` and `keystore_path` onto the now-correct scoped accessor) remain open — this Step fixes the taxonomy's own resolution, not its two production consumers.
