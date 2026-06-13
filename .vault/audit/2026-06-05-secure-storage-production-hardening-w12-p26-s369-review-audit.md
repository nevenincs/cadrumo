---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S369]]'
---

# `secure-storage-production-hardening` `W12.P26.S369` Review

## S369-001 | PASS | Transaction repository remains bound to runtime-created secure storage

`TransactionCatalogueRepository` resolves its default secure-object repository through
`inspect_bucket_storage_runtime(bucket_id, load_settings()).secure_object_repository()`.
The migrated-runtime gate covers transaction repositories in missing-session,
route/session mismatch, and active-profile isolation scenarios, so default construction
fails closed unless the secure bucket runtime is ready for the requested bucket.

## S369-002 | PASS | Inner-envelope integrity failures are structured AEAT errors

The transaction catalogue load path now passes decrypted bytes directly to Pydantic and
keeps schema drift wrapped in `StoredTransactionDriftError`. Inner envelope
classification and schema-version drift now raise storage-layer AEAT exceptions with
`translated_message` keys and structured context instead of literal-only messages.

## S369-003 | PASS | Integrity failures are logged before refusal

Classification and schema-version mismatches are logged at error level with the bucket
id, object key, and offending value before the typed storage exception is raised.
Validation drift remains logged with traceback context before it is wrapped.

## S369-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/transactions/_repository.py src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/transactions/test_cross_bucket_isolation.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` passed.
- `uv run --no-sync pytest -q src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/transactions/test_cross_bucket_isolation.py` passed with 13 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "transaction or TransactionCatalogueRepository"` passed with 3 tests and 90 deselected.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with the known PLAN022 warning.
- `uv run --no-sync vaultspec-rag search "TransactionCatalogueRepository inspect_bucket_storage_runtime load_settings secure object runtime default classification version envelope" --type code --port 8766 --max-results 8` returned the repository and storage runtime contract evidence.
- `uv run --no-sync vaultspec-rag search "transaction catalogue secure storage runtime default bucket isolation manifest-bucket secure-object repository" --type code --port 8766 --max-results 8` returned runtime isolation and cross-bucket coverage evidence.

Reviewer note: no critical, high, medium, or low runtime-storage findings remain for
the S369 slice.

Disposition: close `AFR-267` as `runtime-default`.
