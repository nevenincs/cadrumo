---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:fb4cb4b97617c20d3caa8b1abeb56335af1ceff63c4ca18c070626b2b7cd6d0c'
step_id: 'S27'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add keystore_sidecar_path validating keystore separation then joining the sidecar filename, and export it from the bucket package facade, gated by a test asserting an unvalidated separation refuses before any path is returned

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py`

## Description

## Outcome

Landed in `6099f113dd`, confirmed at HEAD. `keystore_sidecar_path(*, storage_root, bucket_id, filename)` in `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py:116-138` calls `validate_keystore_separation` before joining `filename` onto the bucket's keystore directory, and is exported from the bucket package facade (`__all__` at line 141). Gated by `test_sidecar_path_refuses_before_returning_when_separation_invalid` in `bucket/tests/test_keystore_paths.py:87` (positive control) alongside `test_sidecar_path_joins_filename_onto_keystore_directory` at line 82.

## Notes
