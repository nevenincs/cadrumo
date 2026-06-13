---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S413'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P33.S413`

Promoted storage hierarchy constants and namespace identities into typed registry models.

- Added: `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- Added: `src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/_layout.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/_lockfile.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py`
- Modified: `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py`
- Modified: `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py`
- Modified: `src/aeat/adapters/persistence/storage/attachment.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/_master_key.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`
- Modified: `src/aeat/application/user_profile/_profile_repository.py`

## Description

Added strict frozen Pydantic registry models for secure-object namespace definitions, storage path definitions, and the combined hierarchy registry. The registry now enforces unique namespace keys, unique namespace values, path-key uniqueness, safe namespace strings, safe singleton object keys, and named schema versions for blob/secret/secure-object contracts.

Storage helpers now derive bucket path segments, manifest/lock names, keystore segments, the wrapped bucket DEK filename, blob manifest schema version, secret record schema version, attachment namespaces, and unsecured-profile guard lookup values from the registry.

## Tests

Passed:

- `uv run ruff check` on the W15.P33 storage and application slices
- `uv run pytest -q ...` W15.P33 focused 205-test slice
