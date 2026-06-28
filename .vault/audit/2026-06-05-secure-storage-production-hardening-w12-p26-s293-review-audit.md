---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S293-001 | PASS | Adapter registry owns master-key runtime errors

`src/aeat/core/errors/registry/_adapters.py` declares the storage master-key runtime
errors with explicit registry rows: unavailable master key, unsupported KDF version,
locked keychain, passphrase mismatch, missing key material, missing active bucket
session, reentrant master-key provider entry, and master-key type mismatch. The rows
route through stable `AUTH`, `LOCKED`, `REFUSED`, and `INTERNAL` categories and carry
locale message keys rather than user-facing literal strings.

Disposition: close `AFR-191` as a runtime-default registry boundary after reclassifying
the OS-keychain locked master-key row to the shared `LOCKED` category.

## S293-002 | PASS | Exception hierarchy is registry-bound

The audited storage exceptions derive through `SecretStoreError` or `StorageError`,
which derive from `SecureStorageError` and ultimately `AeatError`. The active-session
failure `NoActiveBucketSessionError` derives from `SecretStoreError` and provides the
localized remediation message key used by the CLI envelope.

## S293-003 | PASS | Duplication search found the canonical surface

Vaultspec RAG clustered the queried master-key registry terms back to
`src/aeat/core/errors/registry/_adapters.py`, the master-key provider implementation,
and master-key/config routing tests. No duplicate registry table or second adapter
master-key error-code authority was found.

## S293-004 | PASS | Keychain lock no longer renders as authentication rejection

The prior row categorized `MasterKeyKeychainLockedError` as `AUTH` even though the
runtime state is recoverable by unlocking an OS keychain. The implementation now uses
`LOCKED_STORAGE_MASTER_KEY_KEYCHAIN`, `ErrorCategory.LOCKED`, and
`errors.locked.locked_storage_master_key_keychain`. A real test constructs the
production error, builds the envelope, and renders operator text to pin the `Locked.`
prefix.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/errors/registry/_adapters.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py`
- `uv run --no-sync pytest -q src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_kdf_errors.py src/aeat/adapters/persistence/storage/master_key/test_dek_wrap_errors.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "storage master key keychain locked error registry locked category locale" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "MasterKeyKeychainLockedError GoogleAuthKeychainLockedError BucketLockedError ErrorCategory LOCKED" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
