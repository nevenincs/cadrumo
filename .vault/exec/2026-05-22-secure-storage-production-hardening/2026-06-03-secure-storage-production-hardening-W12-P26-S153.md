---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S153'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s153-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S153`

Closed `AFR-051` for the encrypted blob store plaintext-exception surface.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py` against the `master-key` and `plain-file` scanner signals.
- Kept the plaintext exception limited to `SensitivityClass.CORPUS`; non-CORPUS blob writes still encrypt payload bytes and wrap per-blob DEKs under the active master key.
- Centralized blob layout constants through the storage namespace registry's `blob_manifest` grammar.
- Added strict lowercase SHA-256 validation for `BlobReference` and `BlobManifest` digest fields so path-bearing and non-hex values cannot enter filesystem path composition.
- Added localized blob not-found and integrity helpers with structured context and no raw paths or digests in operator-facing exceptions.
- Wrapped direct manifest `get()` loads in localized blob integrity errors so malformed manifest files cannot escape as raw parser or pydantic failures.
- Replaced path-bearing blob-store logs with path markers and error types.
- Changed corrupt manifest iteration from log-and-skip to fail-closed `BlobIntegrityError`.
- Corrected the ciphertext layout documentation to state that ciphertext payload files are addressed by the plaintext digest path while the manifest records the ciphertext digest.
- Corrected active master-key documentation to state that the default path uses the active bucket session.
- Updated the sensitive-write allowlist text to explicitly document CORPUS plaintext only; all non-CORPUS blobs are ciphertext.
- Closed `W12.P26.S153` through `vaultspec-core vault plan step check` and aligned `AFR-051` to `closed`; `AFR-052` / `W12.P26.S154` remain pending.
- Completed a final reviewer pass with no findings after direct manifest load localization and ciphertext layout documentation fixes.

## Outcome

`AFR-051` is closed as a `plaintext-exception`: the only plaintext write is the documented CORPUS-class blob path. Sensitive blob writes remain encrypted and master-key backed.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/blob_store/test_blob_store.py src/aeat/adapters/persistence/storage/test_rotation.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py -k "BlobStore or blob_store or blob or sensitive_direct_write"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/blob_store/_blob_store.py src/aeat/adapters/persistence/storage/blob_store/test_blob_store.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local `Path("db://secure_objects")` construction, direct settings construction, or direct environment access.

## Notes

Explorer review identified the digest validation path-traversal risk, stale active master-key documentation, missing instance-level localization, corrupt manifest swallowing, and imprecise plaintext-exception allowlist wording. All were addressed in this step.
