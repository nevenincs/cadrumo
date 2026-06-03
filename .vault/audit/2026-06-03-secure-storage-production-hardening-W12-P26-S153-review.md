---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S153]]'
---

# `secure-storage-production-hardening` `W12.P26.S153` Review

## S153-001 | PASS | Blob store file IO is the accepted encrypted side-store boundary

`src/aeat/adapters/persistence/storage/blob_store/_blob_store.py` owns the encrypted blob payload side-store rooted at `Settings.aeat_blob_store_dir`. The direct file operations are the substrate itself: atomic writes stage into the target shard directory, replace into place, and fsync the parent directory; reads validate manifest and payload hashes before returning plaintext.

The plaintext path is restricted to `SensitivityClass.CORPUS`, whose classification policy requires plaintext at rest. Every other sensitivity class is encrypted with a fresh per-blob DEK, the DEK is wrapped under the active master key or injected provider, and the manifest records the payload/wrapped-key metadata.

## S153-002 | PASS | Master-key and exception boundaries stay typed

Master-key access goes through `get_active_master_key()` or an injected `MasterKeyProvider`. Missing payloads raise `BlobNotFoundError`; digest, manifest, and decrypted-payload mismatches raise `BlobIntegrityError`; unsupported envelope versions raise `EnvelopeVersionError`; decryption failures remain `DecryptionError`. These derive from the AEAT persistence hierarchy.

Corrupt manifest iteration is intentionally not fatal: the iterator logs the skipped manifest with warning-level evidence and continues so one broken sidecar does not block every other blob. Rotation paths likewise log decrypt/write failures and return counted errors rather than silently dropping them.

## S153-003 | PASS | Tests exercise the real blob substrate

The focused tests use the real `EncryptedBlobStore` with real `EphemeralMasterKeyProvider` keys and filesystem-backed temp roots. They prove CORPUS plaintext behavior, ciphertext behavior for sensitive classes, wrapped DEK manifests, missing/tampered failures, deletion semantics, manifest iteration, and master-key isolation. No fakes, mocks, stubs, monkeypatches, skips, or xfails are used.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/blob_store/test_blob_store.py` passed with 17 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/blob_store/_blob_store.py src/aeat/adapters/persistence/storage/blob_store/test_blob_store.py` passed.
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local secure-object marker construction, direct settings construction, or direct environment access.

Disposition: close `AFR-051` as `plaintext-exception`.
