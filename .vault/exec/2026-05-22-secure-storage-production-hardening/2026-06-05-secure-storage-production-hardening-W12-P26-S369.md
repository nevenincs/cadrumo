---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S369'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S369 - Close AFR-267 for transaction repository

Scope: close `AFR-267` for `src/aeat/domain/transactions/_repository.py` with signals
`secure-object, runtime, manifest-bucket`, target `runtime-default`, and owner
`W12.P21.S84`.

## Description

- Audited `TransactionCatalogueRepository` against the runtime secure bucket factory.
- Confirmed default construction resolves through `inspect_bucket_storage_runtime` and
  `load_settings` rather than naked environment access or direct SQL construction.
- Preserved encrypted FINANCIAL secure-object storage under the transaction bucket
  namespace.
- Passed decrypted envelope bytes directly to Pydantic during load.
- Converted inner-envelope classification and schema-version drift to structured
  storage AEAT exceptions with translated message keys and context payloads.
- Added real encrypted-storage tests that mutate persisted inner envelope metadata and
  assert structured classification and schema-version errors.
- Closed `W12.P26.S369` through `vaultspec-core vault plan step check` and updated the
  `AFR-267` register status to `closed`.

## Outcome

`AFR-267` is closed. The transaction catalogue repository remains runtime-default over
secure bucket storage, preserves bucket isolation, and now reports inner envelope
integrity failures through structured AEAT storage exceptions.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/transactions/_repository.py src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/transactions/test_cross_bucket_isolation.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `uv run --no-sync pytest -q src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/transactions/test_cross_bucket_isolation.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "transaction or TransactionCatalogueRepository"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
- `uv run --no-sync vaultspec-rag search "TransactionCatalogueRepository inspect_bucket_storage_runtime load_settings secure object runtime default classification version envelope" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "transaction catalogue secure storage runtime default bucket isolation manifest-bucket secure-object repository" --type code --port 8766 --max-results 8`

## Notes

This step avoided S298 and the previously active modelos files. No translation file was
edited; existing storage integrity locale keys cover the new structured exception
surfaces, and the locale audit was run through `python -m aeat.locales`.
