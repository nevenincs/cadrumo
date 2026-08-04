---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:cb5957c048087ced78b0e1ba0f0de495e87313d0b1a997adf5dd0187ddf89000'
step_id: 'S21'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point keystore_path onto the scoped accessor while preserving the keystore-separation validation, gated by the existing separation-refusal test

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py`

## Description

- Establish the real keystore layout from `validate_keystore_separation`'s
  own refusal logic before touching anything: `<root>/keystore/<bucket_id>/`,
  sibling to `<root>/buckets/`, deliberately not read off the taxonomy
  declaration or a test. Confirmed `storage_location(StorageCategory.
  BUCKET_KEYSTORE).relative_path()` resolves to exactly that shape (`root /
  "keystore" / bucket_id`) via direct computation, matching what
  `KEYSTORE_DIRNAME` already resolved to.
- Re-point `keystore_root` to read `storage_location(StorageCategory.
  BUCKET_KEYSTORE).relative_path()` instead of the `_namespace_registry`
  -bridged `KEYSTORE_DIRNAME`.
- Re-point `validate_keystore_separation`'s `buckets_parent` to
  `paths.bucket_dir.parent` -- the already-resolved `bucket_paths()` result
  -- instead of a second read of the governed "buckets" name, removing a
  duplicate rather than adding one.
- Leave the separation-refusal logic itself (the `_is_under` checks against
  `paths.db_dir` and `buckets_parent`) completely untouched.

## Outcome

Confirmed byte-identical resolution for `keystore_root`, `keystore_path`,
and that `validate_keystore_separation` still refuses a keystore configured
under the bucket db dir. Full bucket, storage, and dependent application
suites re-run clean (1192 + 897 passed across separate runs).

## Notes

None. No skipped work, no scaffolds left in code. Landed together with S20
in commit 64a4e3ab1e.
