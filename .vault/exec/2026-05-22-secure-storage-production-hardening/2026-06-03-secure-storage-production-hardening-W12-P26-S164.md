---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S164'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s164-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S164`

Closed `AFR-062` for the AEAD/HKDF crypto primitive implementation.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/crypto/_crypto.py` against the `master-key` scanner signal.
- Replaced broad `except Exception` wrappers around AESGCM encrypt/decrypt and HKDF derivation with explicit `(TypeError, ValueError)` catches.
- Preserved `InvalidTag` as the dedicated authentication-failure arm for decrypt.
- Removed unreachable `pragma: no cover` exception wrappers from the crypto primitive boundary.
- Added direct runtime-boundary tests for invalid plaintext type, invalid associated-data type, and invalid HKDF context type.
- Confirmed the wrapper does not log, persist, or expose key bytes, plaintext bytes, ciphertext bytes, nonce bytes, passphrases, or wrapped DEKs.
- Closed `S164` through `vaultspec-core vault plan step check` and updated `AFR-062` to closed.

## Outcome

`AFR-062` is closed as `runtime-default`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/crypto/test_crypto.py src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/crypto/_crypto.py src/aeat/adapters/persistence/storage/crypto/test_crypto.py src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py`
- Touched-surface hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.

## Notes

No modelo export evidence or workbook parity behavior is implemented in this row. The new export ADR constraints remain applicable to later export rows; this row only governs local at-rest crypto primitives.
