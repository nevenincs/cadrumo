---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S156]]'
---

# `secure-storage-production-hardening` `W12.P26.S156` Review

## S156-001 | PASS | Bucket errors derive from the secure-storage AEAT base

`src/aeat/adapters/persistence/storage/bucket/_errors.py` defines `BucketError` as a `SecureStorageError` subclass. `SecureStorageError` derives from the central `AeatError`, so bucket lifecycle, manifest validation, lock, and recovery failures remain catchable through the core AEAT exception hierarchy.

Existing tests assert every exported bucket error class inherits from `AeatError`, carries a registered error code, and builds a round-trippable error envelope. S156 hardened this coverage by adding `BucketValidationError` to the direct inheritance, registered-code, and distinct-code checks.

## S156-002 | PASS | Operator-facing bucket lifecycle errors are registry-localized

`NoActiveBucketError`, `BucketBusyError`, `BucketAlreadyPresentError`, `BucketLockedError`, `RecoveryUnavailableError`, and `RecoveryVerificationError` pass `translated_message` keys into the base class. The keys are present in all locale catalogues as verified by the `aeat.locales` CLI audit.

`BucketValidationError` intentionally inherits the base message behavior because concrete layout, manifest, and keystore validators supply the validation detail at the call site; it still remains registry-bound as an AEAT bucket validation error.

## S156-003 | PASS | Scanner signals are discovery, not a storage bypass

The `manifest-bucket` and `master-key` signals in this file are type-surface references. The module declares the errors that surrounding manifest, lock, recovery, and master-key flows raise; it does not read manifests, open buckets, unwrap keys, write files, consult settings, or inspect environment variables.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py` passed with 29 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_errors.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` reported `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` ok.
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.
- Plan state was reconciled after the CLI checked S156 but left `AFR-054` pending; the repaired state is `AFR-054`/`S156` closed and `AFR-055` through `AFR-057` / `S157` through `S159` pending.

Disposition: close `AFR-054` as `manifest-discovery`.
