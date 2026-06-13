---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S164]]'
---

# `secure-storage-production-hardening` `W12.P26.S164` Review

## S164-001 | PASS | AEAD/HKDF wrapper failures are no longer broad catches

`src/aeat/adapters/persistence/storage/crypto/_crypto.py` no longer uses `except Exception` or `pragma: no cover` around AESGCM encrypt/decrypt or HKDF derivation. The wrapper now catches the observable cryptography 47.0.0 Rust-binding boundary failures, `TypeError` and `ValueError`, while preserving the explicit `InvalidTag` arm for authentication failure.

The replacement keeps all public failures inside the AEAT storage hierarchy: `EncryptionError`, `DecryptionError`, and `KeyDerivationError`.

## S164-002 | PASS | Error messages do not expose secret material

The narrowed wrappers include only cryptography exception text such as invalid argument class or invalid nonce size. Existing key-length guards report lengths only. No key bytes, plaintext bytes, nonce bytes, ciphertext bytes, associated-data bytes, passphrases, wrapped DEKs, or local paths are added to messages or context.

## S164-003 | PASS | Tests exercise real boundary failures

`src/aeat/adapters/persistence/storage/crypto/test_crypto.py` now includes real invalid-runtime-input tests for AESGCM encryption, AESGCM decryption, and HKDF derivation. The tests call the production wrapper functions directly and assert the AEAT error classes, without mocks, monkeypatching, fakes, stubs, skip, or xfail.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/crypto/test_crypto.py src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py` passed with 73 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/crypto/_crypto.py src/aeat/adapters/persistence/storage/crypto/test_crypto.py src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py` passed.
- Touched-surface hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.

Review-agent note: spawning `vaultspec-code-reviewer` for this row failed with the current agent thread limit, so the formal review was completed locally using the same checklist.

Disposition: close `AFR-062` as `runtime-default`.
