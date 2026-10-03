---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:eac603b6b49bfabae4380d8901a3f2e93f5c74190ea4545f1abf7224f97f4cea'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S190` Review

## S190-001 | PASS | Aggregation module does not own storage persistence

`_iva_ledger.py` performs IVA observation projection from transaction catalogues. It does not open files, create manifests, read environment variables, or maintain a separate storage route.

## S190-002 | PASS | Repository-backed path delegates to the transaction catalogue repository

`aggregate_iva_ledger_observations_from_repositories` either uses the injected repository or creates `TransactionCatalogueRepository(bucket_id=...)`. That keeps secure-object storage and bucket routing in the domain repository rather than duplicating persistence rules inside aggregation.

## S190-003 | PASS | Transaction repository default is runtime-routed

`TransactionCatalogueRepository` resolves its default secure-object repository through `inspect_bucket_storage_runtime(bucket_id, load_settings()).secure_object_repository()`. The IVA ledger aggregation path therefore reaches persisted transactions through the sanctioned runtime attachment rather than direct SQL-route construction.

## S190-004 | PASS | Bucket mismatch is fail-closed and localized

The repository-backed entry point refuses a repository whose `bucket_id` differs from the requested bucket before loading data. The failure uses `AggregationValidationError` with the `aggregation.iva_ledger.errors.bucket_mismatch` translation key and structured bucket context.

## S190-005 | PASS | Repository integrity exceptions are logged or chained

Transaction catalogue load does not silently swallow integrity or schema failures: classification/version errors are logged and re-raised, and pydantic drift is wrapped as `StoredTransactionDriftError` with the original validation exception chained.

Validation:

- the historical check passed with 33 tests.
- the historical check passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- The S190 hygiene scan found no env access, monkeypatches, fakes, stubs, mocks, suppressions, broad exception swallowing, or runtime pragma shortcuts in the reviewed slice. The only match was an existing `TYPE_CHECKING` import-cycle guard in the transaction repository.

Reviewer note: Heisenberg review found no issues in the S190 closure evidence. The remaining `IvaLedgerAggregationIssue.detail` strings are structured diagnostic issue payloads, not thrown exceptions; if they become direct CLI output, they should be reviewed in a dedicated operator-message localization pass.

Disposition: close `AFR-088`.
