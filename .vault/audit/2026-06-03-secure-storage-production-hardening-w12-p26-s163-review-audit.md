---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S163]]'
---

# `secure-storage-production-hardening` `W12.P26.S163` Review

## S163-001 | PASS | Crypto facade does not persist key material

`src/aeat/adapters/persistence/storage/crypto/__init__.py` is a package facade. It imports and re-exports AEAD constants, `EncryptedBlob`, `derive_key`, `encrypt_record`, `decrypt_record`, and the encrypted SQLAlchemy column types.

The facade does not construct a master key, read settings, read environment variables, create storage routes, write files, write SQL rows, serialize passphrases, persist wrapped DEKs, or bypass the active bucket session. The `master-key` scanner signal is accepted because the facade names crypto primitives whose implementations live in `_crypto.py` and `_encrypted_columns.py`; this file itself has no custody behavior.

## S163-002 | PASS | Runtime-default resolution remains delegated

The module docstring correctly states that column-level encrypt/decrypt operations resolve key bytes through the active `BucketSession`. The facade does not import active-session internals directly or create alternate runtime-default resolution.

`AFR-062` / `W12.P26.S164` remains the implementation row for `_crypto.py`; encrypted-column runtime behavior is covered by existing crypto tests and later rows where the owning implementation files appear.

## S163-003 | PASS | Tests are behavioral and non-tautological

The direct tests exercise AEAD roundtrips, tamper detection, key-size validation, wire-shape parsing, HKDF derivation, SQLAlchemy encrypted-column persistence, cross-type replay prevention, hashed lookup behavior, and ciphertext-on-disk assertions. They use real cryptographic operations and a real in-memory SQLAlchemy engine. No fake/stub class, mock import, monkeypatch, skip, xfail, direct settings construction, or direct environment access was found in the reviewed facade or direct tests.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/crypto/test_crypto.py src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py` passed with 70 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/crypto/__init__.py src/aeat/adapters/persistence/storage/crypto/test_crypto.py src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py` passed.
- Touched-surface hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.

Review-agent note: spawning `vaultspec-code-reviewer` for this row failed with the current agent thread limit, so the formal review was completed locally using the same checklist.

Disposition: close `AFR-061` as `runtime-default` facade metadata.
