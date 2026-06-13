---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S437'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S437`

## Description

- Wrapped legacy `EncryptedString` object-key migration UTF-8 decode failures in `DecryptionError`.
- Kept corrupted legacy ciphertext on the AEAT storage exception boundary instead of leaking raw `UnicodeDecodeError`.
- Added a real crypto test that seals invalid UTF-8 plaintext with the legacy string AAD and decrypts it through the migration helper.

## Outcome

Closed.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py` passed with 65 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed.
