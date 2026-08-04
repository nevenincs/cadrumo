---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:b120c04c4ceb911e8609e42c7fbebf3edf5e850c74624e0f76860980cb0caabf'
step_id: 'S20'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point bucket_paths onto the scoped accessor, gated by the existing bucket provisioning tests plus an assertion that no bare directory-name literal survives in the module

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_layout.py`

## Description

- Interpret "the scoped accessor" as `storage_location(StorageCategory.X)`
  read directly, following the idiom already established elsewhere in this
  package (`master_key/_master_key.py`, `_rotation.py`) for explicit-root,
  no-IO path composition -- not `bucket_scoped_storage_path`, which resolves
  its root from settings and would have forced a signature change across the
  53+ call sites depending on `bucket_paths`' explicit-root contract.
- Re-point `bucket_paths` to read `storage_location(StorageCategory.BUCKETS
  / BUCKET_DATABASE / BUCKET_BLOBS / BUCKET_AUDIT).relative_path()` instead
  of the four `_namespace_registry`-bridged named constants.
- Confirm byte-identical resolution before and after for every path this
  touches.
- Add a structural AST test to `test_layout.py` confirming no bare
  directory-name literal survives in `_layout.py`, matching the shape of the
  core name-unification gate. Mutation-proven against a synthetic pre-fix
  snippet rather than by mutating the shared production file in place.

## Outcome

`_layout.py` no longer imports from the `_namespace_registry` re-export
bridge at all; every directory-run literal is now a single read of the core
taxonomy. Full bucket, storage, and dependent application suites re-run
clean (1192 + 897 passed across separate runs).

## Notes

None. No skipped work, no scaffolds left in code. Landed together with S21
in commit 64a4e3ab1e.
