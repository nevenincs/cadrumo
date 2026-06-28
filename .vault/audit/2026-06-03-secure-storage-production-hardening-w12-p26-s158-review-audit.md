---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S158]]'
---

# `secure-storage-production-hardening` `W12.P26.S158` Review

## S158-001 | FIXED BEFORE COMMIT | Keystore separation errors do not leak local paths

`validate_keystore_separation()` previously embedded the configured keystore path and comparison parent path directly in `BucketValidationError` messages. Those paths can reveal local profile roots, usernames, workspace names, or bucket layout details when surfaced through logs, CLI errors, or test diagnostics.

Resolution: separation failures now use stable invariant messages only and carry structured context with `surface=bucket_keystore` and a reason code. Tests verify neither the configured path nor the AEAT root path appears in `str(error)` or the structured error envelope.

## S158-002 | FIXED BEFORE COMMIT | Bucket validation errors are locale-enrolled

`BucketValidationError` was registered in the central AEAT error registry, but detail-bearing instances did not set `translated_message`; renderer resolution could therefore prefer the raw detail message.

Resolution: `BucketValidationError` now sets `translated_message="errors.integrity.integrity_storage_bucket_validation"` while preserving the detail string as the exception argument for compatibility with validator tests and debug assertions.

## S158-003 | PASS | Keystore helpers remain pure manifest-discovery path guards

The module derives `keystore` paths from centralized storage hierarchy constants and validates that configured keystore paths are not under the buckets parent or per-bucket database directory. It does not create directories, read or write key material, access settings or environment variables, open manifests, or touch the master key.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_keystore_paths.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py` passed with 38 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py src/aeat/adapters/persistence/storage/bucket/_errors.py src/aeat/adapters/persistence/storage/bucket/test_keystore_paths.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` reported `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` ok.
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw encoding literals, direct settings construction, or direct environment access.
- Plan state was reconciled after the CLI checked S158 but left `AFR-056` pending; the repaired state is `AFR-056`/`S158` closed and `AFR-057` through `AFR-059` / `S159` through `S161` pending.

Disposition: close `AFR-056` as `manifest-discovery`.
