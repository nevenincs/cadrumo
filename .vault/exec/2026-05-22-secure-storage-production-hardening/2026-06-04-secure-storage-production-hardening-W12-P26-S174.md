---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S174'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s174-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S174`

Closed `AFR-072` for DEK wrap/unwrap primitives.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py` against the `manifest-bucket` scanner signal and `bootstrap-custody` target.
- Wrapped AES-GCM unwrap tag failures in `DecryptionError` so third-party cryptography exceptions do not escape the storage boundary.
- Preserved original `InvalidTag` causes for diagnostics without exposing bucket ids, paths, key material, nonce, ciphertext, or tag values in user-facing messages.
- Converted AES-GCM wrap type/value failures to `EncryptionError`.
- Updated direct tests to assert typed storage decryption failures and cause chaining.

## Outcome

`AFR-072` is closed as a `bootstrap-custody` DEK-wrap implementation row.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_dek_wrap.py src/aeat/adapters/persistence/storage/master_key/test_dek_wrap_errors.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py src/aeat/adapters/persistence/storage/master_key/test_dek_wrap.py src/aeat/adapters/persistence/storage/master_key/test_dek_wrap_errors.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-surface hygiene scan found no broad exception suppressions, direct settings construction, naked environment access, fake/stub/monkeypatch markers, skipped/xfail tests, or direct output.

## Notes

The cryptographic behavior remains grounded in the existing AES-GCM known-answer vector and live roundtrip/tamper tests. The change only narrows the public exception surface to the AEAT storage hierarchy.
