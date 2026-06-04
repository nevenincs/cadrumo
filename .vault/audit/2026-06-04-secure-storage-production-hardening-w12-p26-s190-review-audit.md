---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S190]]'
---

# `secure-storage-production-hardening` `W12.P26.S190` Review

## S190-001 | PASS | Aggregation module does not own storage persistence

`_iva_ledger.py` performs IVA observation projection from transaction catalogues. It does not open files, create manifests, read environment variables, or maintain a separate storage route.

## S190-002 | PASS | Repository-backed path delegates to the transaction catalogue repository

`aggregate_iva_ledger_observations_from_repositories` either uses the injected repository or creates `TransactionCatalogueRepository(bucket_id=...)`. That keeps secure-object storage and bucket routing in the domain repository rather than duplicating persistence rules inside aggregation.

## S190-003 | PASS | Bucket mismatch is fail-closed and localized

The repository-backed entry point refuses a repository whose `bucket_id` differs from the requested bucket before loading data. The failure uses `AggregationValidationError` with the `aggregation.iva_ledger.errors.bucket_mismatch` translation key and structured bucket context.

Validation:

- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_iva_ledger.py` passed with 24 tests.
- `uv run --no-sync ruff check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Reviewer note: supervisor review found no critical or high issues in the S190 slice. The remaining `IvaLedgerAggregationIssue.detail` strings are structured diagnostic issue payloads, not thrown exceptions; if they become direct CLI output, they should be reviewed in a dedicated operator-message localization pass.

Disposition: close `AFR-088`.
