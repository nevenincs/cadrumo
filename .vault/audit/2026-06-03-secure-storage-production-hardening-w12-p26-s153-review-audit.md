---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S153]]'
---

# `secure-storage-production-hardening` `W12.P26.S153` Review

## S153-001 | PASS | Plaintext exception is explicit and bounded

`EncryptedBlobStore.put()` still writes plaintext only when `classification is SensitivityClass.CORPUS`. Every non-CORPUS class follows the ciphertext path with a per-blob DEK wrapped by the active master key. The sensitive-write policy text now says this explicitly instead of describing blob writes generically.

## S153-002 | FIXED BEFORE COMMIT | Digest fields are now path-safe

The initial S153 review found that 64-character digest fields accepted separators, dot tokens, uppercase, and non-hex characters before composing filesystem paths.

Resolution: `BlobReference` and `BlobManifest` now validate SHA-256 fields as lowercase hex. Real validation tests cover separator, dot-token, uppercase, and non-hex rejection.

## S153-003 | PASS | Blob layout derives from the central registry

The blob-store path constants now derive the `blobs` directory and manifest suffix from the `blob_manifest` storage path grammar. This keeps the concrete file layout anchored to the central namespace registry instead of duplicating literal path segments in the adapter.

## S153-004 | FIXED BEFORE COMMIT | Blob errors are localized and redacted

Blob not-found and integrity paths previously raised raw English messages with absolute paths and content digests.

Resolution: the blob store now constructs `BlobNotFoundError` and `BlobIntegrityError` with registered locale keys and structured context. Tests verify missing-manifest and digest-drift paths do not expose root paths or digests through the exception envelope.

## S153-005 | FIXED BEFORE COMMIT | Corrupt manifest iteration fails closed

`iter_manifests()` previously logged and skipped unparseable manifests, which let rotation and inventory flows undercount corrupt blob manifests.

Resolution: corrupt manifest parsing now logs only a redacted path marker and raises localized `BlobIntegrityError`. A real corrupt-manifest test asserts fail-closed behavior and checks that logs omit the full manifest path.

## S153-006 | FIXED BEFORE COMMIT | Direct manifest loads localize corrupt manifests

The reviewer found that `get()` still used the generic envelope loader directly, so malformed manifest JSON or invalid manifest digest fields could escape as raw parser or pydantic errors.

Resolution: direct manifest loads now use the blob-store manifest loader wrapper. Classification drift, schema-version drift, malformed JSON, filesystem read errors, and pydantic validation failures are converted into localized `BlobIntegrityError` with redacted structured context. A real direct-`get()` corrupt-manifest test covers the boundary.

## S153-007 | PASS | Default master-key path is documented and tested

The constructor docstring now matches implementation: when a provider is not injected, the store uses the active bucket session's data-encryption key. Tests cover failure outside an active session and successful ciphertext roundtrip inside `activate_session()`.

## S153-008 | PASS | Ciphertext layout documentation is precise

The module documentation now states the actual layout: ciphertext payload files are stored under the plaintext digest path with the `.enc` suffix, while the manifest records the ciphertext digest for integrity verification.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/blob_store/test_blob_store.py src/aeat/adapters/persistence/storage/test_rotation.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py -k "BlobStore or blob_store or blob or sensitive_direct_write"` passed with 37 selected tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/blob_store/_blob_store.py src/aeat/adapters/persistence/storage/blob_store/test_blob_store.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local `Path("db://secure_objects")` construction, direct settings construction, or direct environment access.
- Final focused reviewer pass returned no findings after direct manifest load localization and ciphertext layout documentation fixes.

Disposition: close `AFR-051` as `plaintext-exception`.
