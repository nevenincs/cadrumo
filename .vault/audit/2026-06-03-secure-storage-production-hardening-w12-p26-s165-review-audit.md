---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S165]]'
---

# `secure-storage-production-hardening` `W12.P26.S165` Review

## S165-001 | PASS | Column validation failures carry a locale key

`src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py` now centralizes column-boundary `StorageValidationError` construction through a helper carrying `translated_message="errors.integrity.integrity_storage_validation"`.

The helper is used for invalid encrypted string values, invalid encrypted bytes values, non-JSON-serializable encrypted JSON values, invalid hashed-lookup plaintext values, invalid pre-computed digest lengths, invalid bind value types, and invalid stored digest lengths. `uv run --no-sync -q python -m aeat.locales audit` passed for all locale files.

## S165-002 | PASS | Stored invalid UTF-8/JSON failures stay in AEAT errors

`EncryptedString.process_result_value` now wraps decoded invalid UTF-8 in `DecryptionError`, matching the existing legacy string helper. `EncryptedJSON.process_result_value` wraps invalid decrypted UTF-8 or invalid decrypted JSON in `DecryptionError` instead of leaking `UnicodeDecodeError` or `json.JSONDecodeError` out of the storage boundary.

The error strings identify the failed storage shape and do not include key bytes, plaintext bytes, ciphertext bytes, nonce bytes, associated-data bytes, passphrases, wrapped DEKs, or local paths.

## S165-003 | PASS | Runtime-default key resolution remains centralized

Column encrypt/decrypt and hashed lookup computation still resolve key bytes through `_resolve_master_key`, which delegates to `get_active_master_key`. The row does not introduce direct settings construction, direct environment access, alternate key providers, SQL route construction, or local secure-object marker construction.

## S165-004 | PASS | Tests exercise real encrypted payload boundaries

The tests use real `EphemeralMasterKeyProvider` sessions, AESGCM encryption, SQLAlchemy type decorators, and an in-memory SQLAlchemy engine. New coverage verifies translated validation keys, invalid stored JSON as `DecryptionError`, invalid stored string UTF-8 as `DecryptionError`, and invalid hashed lookup input as localized `StorageValidationError`.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py src/aeat/adapters/persistence/storage/crypto/test_crypto.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed with 118 tests and 3 known SQLAlchemy sqlite datetime adapter deprecation warnings.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py src/aeat/adapters/persistence/storage/crypto/test_crypto.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Touched-surface hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.

Review-agent note: spawning `vaultspec-code-reviewer` for this row failed with the current agent thread limit, so the formal review was completed locally using the same checklist.

Disposition: close `AFR-063` as `runtime-default`.
