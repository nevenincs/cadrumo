---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S165'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s165-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S165`

Closed `AFR-063` for SQLAlchemy encrypted-column runtime-default behavior.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py` against the `secure-object`, `master-key`, and `sql-route` scanner signals.
- Centralized encrypted-column `StorageValidationError` creation with the existing `errors.integrity.integrity_storage_validation` locale key.
- Wrapped invalid decrypted `EncryptedString` UTF-8 and invalid decrypted `EncryptedJSON` UTF-8/JSON in `DecryptionError`.
- Confirmed active key resolution remains delegated through `get_active_master_key`.
- Added real encrypted payload tests for invalid stored UTF-8, invalid stored JSON, translated validation keys, and invalid hashed-lookup input.
- Closed `S165` through `vaultspec-core vault plan step check` and updated `AFR-063` to closed.

## Outcome

`AFR-063` is closed as `runtime-default`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py src/aeat/adapters/persistence/storage/crypto/test_crypto.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py src/aeat/adapters/persistence/storage/crypto/test_crypto.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-surface hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.

## Notes

No modelo export evidence or workbook parity behavior is implemented in this row. The new export ADR constraints remain applicable to later export rows; this row only governs local SQLAlchemy encrypted-column storage behavior.
