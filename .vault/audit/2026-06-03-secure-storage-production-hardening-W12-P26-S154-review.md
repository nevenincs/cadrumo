---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S154]]'
---

# `secure-storage-production-hardening` `W12.P26.S154` Review

## S154-001 | PASS | Secret materialisation is an explicit plaintext bridge

`src/aeat/adapters/persistence/storage/blob_store/_materialisation.py` exists for third-party APIs that require a filesystem path rather than in-memory bytes. It reads secret bytes from `SecretStore`, writes them to a short-lived tempfile through the `mkstemp` file descriptor, yields or returns the path, and removes the file during cleanup.

This is a `plaintext-exception`, not an alternate persistence backend: the secret source remains the encrypted blob/secret store, and the plaintext file is temporary consumer interop.

## S154-002 | PASS | Settings and master-key resolution stay centralized

The singleton factory resolves directories from `load_settings()` or a caller-supplied `Settings` object. It constructs `EncryptedBlobStore` and `SecretStore` from those centralized settings paths and does not read environment variables directly or construct settings ad hoc.

Master-key access stays below the store layer: `EncryptedBlobStore` falls through to the active bucket session when no provider is injected.

## S154-003 | PASS | Cleanup suppressions are narrow and tested

The only suppressions are `contextlib.suppress(FileNotFoundError)` around cleanup unlink calls. They make cleanup idempotent and tolerate a caller or consumer already removing the temp file; they do not hide secret-store, write, or read failures.

## S154-004 | PASS | Export parity ADRs do not widen the materialisation authority

The 2026-06-03 export ADRs require ledger-derived modelo exports to carry bundled or resolvable evidence, offline and Sheets exports to share one typed export plan with registry-grounded parity gates, documentary parity to avoid fake executable runners for layout-only modelos, and BOE fichero exports to pair golden SHA with DR-shape assertions.

Those constraints do not change `AFR-052`'s storage disposition. The helper is only a path-shaped transport bridge for already-stored secret bytes; it is not a calculation/export authority, evidence source, workbook builder, or parity oracle. Future export work must keep export content grounded in the encrypted revision/evidence envelope and the shared plan builder, not in this temporary plaintext path.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py` passed with 10 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/blob_store/_materialisation.py src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py` passed.
- Case-sensitive touched-file hygiene scan found no broad exception catches, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local secure-object marker construction, direct settings construction, or direct environment access.
- Suppression scan found only `FileNotFoundError` cleanup suppressions after `mkstemp` materialisation paths.

Disposition: close `AFR-052` as `plaintext-exception`.
