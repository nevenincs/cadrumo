---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S42'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p10-s42-review-audit]]'
---



# `secure-storage-production-hardening` `W05.P10.S42`

Stored remote mirror manifests with ciphertext hashes and revision watermarks,
then resolved the mandatory review findings before closing the row.

- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Modified: `src/aeat/adapters/outbound/storage/__init__.py`
- Modified: `src/aeat/adapters/outbound/storage/_records.py`
- Modified: `src/aeat/adapters/outbound/storage/test_foundation.py`
- Modified: `src/aeat/entrypoints/cli/_config/_google.py`
- Created: `src/aeat/adapters/outbound/storage/_mirror_manifest.py`
- Created: `src/aeat/adapters/outbound/storage/test_mirror_manifest.py`
- Created: `src/aeat/entrypoints/cli/_config/test_google_sync_push.py`
- Created: `.vault/audit/2026-05-28-secure-storage-production-hardening-W05-P10-S42-review.md`

## Description

Raw secure-object iteration now exposes revision ids, previous revision ids,
payload hashes, ciphertext hashes, and revision timestamps without decrypting
payload bytes. The outbound storage layer now has typed remote mirror manifest
records plus helpers to build and persist namespace manifests in the provider
`_sync-state` namespace.

The first review found two HIGH issues: manifest object identifiers did not
match the real mirror push object keys, and the production push path did not
persist manifests. Both were resolved before closure. Manifest entries now use
the same provider object HMAC derivation as the push path, and the Google sync
push helper writes namespace manifests for full non-dry-run pushes after
successful ciphertext object uploads.

## Tests

- `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/__init__.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py`
- `uv run pytest src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py -q`
- `git diff --check -- .vault/audit/2026-05-28-secure-storage-production-hardening-W05-P10-S42-review.md src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/outbound/storage/__init__.py src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py`

Review audit: `2026-05-28-secure-storage-production-hardening-W05-P10-S42-review`.
