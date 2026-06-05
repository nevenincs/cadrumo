---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
step_id: 'S293'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S293 - Close AFR-191 for adapter error registry

Scope: close `AFR-191` for `src/aeat/core/errors/registry/_adapters.py` with signal
`master-key`, target `runtime-default`, and owner `W12.P20.S78`.

## Description

- Audited the adapter error registry rows for storage master-key provider, active
  session, and internal master-key failures.
- Confirmed master-key error rows use central `ErrorCode` declarations and locale
  message keys.
- Confirmed the audited exception classes derive through the secure-storage exception
  hierarchy into `AeatError`.
- Ran vaultspec RAG semantic searches for duplicate master-key registry and provider
  error-code surfaces.
- Closed `W12.P26.S293` through `vaultspec-core vault plan step check` and updated
  the `AFR-191` register status to `closed`.

## Outcome

`AFR-191` is closed as the canonical adapter-registry runtime-default boundary for
master-key errors. No production code change was required for
`src/aeat/core/errors/registry/_adapters.py`.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/errors/registry/_adapters.py src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/core/errors/test_exception_base_hygiene.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/adapters/persistence/storage/master_key/test_cluster_envelopes.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py`
- `uv run --no-sync pytest -q src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/adapters/persistence/storage/master_key/test_cluster_envelopes.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "error registry adapters master key storage runtime default secure storage exceptions translated message key" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "adapter error registry master key FileFallbackMasterKeyProvider Keyring provider StorageValidationError error code" --type code --port 8766 --max-results 8`

## Notes

The broader exception-base hygiene test currently fails on `ModeloIvaWalletSeedError`,
which is already tracked by the plan as `AFR-299` / `W12.P26.S383`. That finding is
outside `AFR-191` and remains pending for its own row.
