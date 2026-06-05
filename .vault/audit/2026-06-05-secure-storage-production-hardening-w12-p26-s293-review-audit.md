---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S293-001 | PASS | Adapter registry owns master-key runtime errors

`src/aeat/core/errors/registry/_adapters.py` declares the storage master-key runtime
errors with explicit registry rows: unavailable master key, unsupported KDF version,
locked keychain, passphrase mismatch, missing key material, missing active bucket
session, reentrant master-key provider entry, and master-key type mismatch. The rows
route through stable `AUTH`, `REFUSED`, and `INTERNAL` categories and carry locale
message keys rather than user-facing literal strings.

Disposition: close `AFR-191` as a runtime-default registry boundary. No production code
change was required for this row.

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

## S293-004 | NOTE | Broader exception-base guard has an already-tracked failure

The full exception-base hygiene gate fails on `ModeloIvaWalletSeedError`, which is
tracked separately in this same plan as `AFR-299` / `W12.P26.S383` for
`src/aeat/application/modelo/_iva_wallet_seed.py`. This is not part of `AFR-191`, but
it remains a required follow-up before the broader exception-base convention is clean.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/errors/registry/_adapters.py src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/core/errors/test_exception_base_hygiene.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/adapters/persistence/storage/master_key/test_cluster_envelopes.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py`
- `uv run --no-sync pytest -q src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/adapters/persistence/storage/master_key/test_cluster_envelopes.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "error registry adapters master key storage runtime default secure storage exceptions translated message key" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "adapter error registry master key FileFallbackMasterKeyProvider Keyring provider StorageValidationError error code" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

Validation note:

- `uv run --no-sync pytest -q src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/core/errors/test_exception_base_hygiene.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/adapters/persistence/storage/master_key/test_cluster_envelopes.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py` failed only on the already-tracked `AFR-299` exception-base violation in `src/aeat/application/modelo/_iva_wallet_seed.py`.
