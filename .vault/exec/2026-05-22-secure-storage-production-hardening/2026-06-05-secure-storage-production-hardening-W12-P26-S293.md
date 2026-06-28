---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
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
- Reclassified `MasterKeyKeychainLockedError` from an `AUTH` registry row to the
  shared `LOCKED` runtime category used by bucket and Google keychain lock errors.
- Moved the master-key keychain locked message from the `errors.auth` locale namespace
  to the `errors.locked` namespace through `python -m aeat.locales`.
- Confirmed the audited exception classes derive through the secure-storage exception
  hierarchy into `AeatError`.
- Added a real envelope/rendering regression proving a locked OS keychain renders with
  a `Locked.` operator prefix and retryable locked-category envelope.
- Ran vaultspec RAG semantic searches for duplicate master-key registry and provider
  error-code surfaces.
- Closed `W12.P26.S293` through `vaultspec-core vault plan step check` and updated
  the `AFR-191` register status to `closed`.

## Outcome

`AFR-191` is closed as the canonical adapter-registry runtime-default boundary for
master-key errors. The registry now treats an OS keychain lock as a locked runtime
state, not an authentication rejection, and the locale catalogues carry the message
under the matching locked namespace.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/errors/registry/_adapters.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py`
- `uv run --no-sync pytest -q src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/adapters/persistence/storage/master_key/test_master_key_errors.py src/aeat/adapters/persistence/storage/master_key/test_kdf_errors.py src/aeat/adapters/persistence/storage/master_key/test_dek_wrap_errors.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "storage master key keychain locked error registry locked category locale" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "MasterKeyKeychainLockedError GoogleAuthKeychainLockedError BucketLockedError ErrorCategory LOCKED" --type code --port 8766 --max-results 8`

## Notes

No deprecated `config init` guidance was introduced in the touched source and locale
surface. The broader plan still carries other exception-base and runtime-enrollment
rows outside `AFR-191`; those remain pending under their own step identifiers.
