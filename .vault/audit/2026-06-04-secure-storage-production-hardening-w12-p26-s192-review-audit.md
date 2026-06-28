---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S192]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
---

# `secure-storage-production-hardening` `W12.P26.S192` Review

## S192-001 | PASS | Renta invoice persistence is bucket-bound

`aggregate_renta_ledger_expenses_from_repositories` now constructs the default
`InvoiceCatalogueRepository` with the requested `bucket_id`, matching the
existing transaction repository scoping. Repository-backed Renta aggregation no
longer lets invoice loading fall back to whichever profile is active in process
settings.

## S192-002 | PASS | Injected invoice repositories fail closed on bucket drift

Injected invoice repositories must report the same bucket as the requested Renta
ledger aggregation bucket. A repository bound to another bucket, or an injected
repository with `bucket_id is None`, raises `AggregationValidationError` with
the localized key `aggregation.renta_ledger.errors.invoice_bucket_mismatch`.

## S192-003 | PASS | Tests exercise real secure storage

The regression tests use real `TransactionCatalogueRepository` and
`InvoiceCatalogueRepository` instances over the secure SQL repository fixture.
No fakes, monkeypatching, environment mutation, or duplicated business logic were
introduced.

## Reviewer Findings

Initial reviewer pass found one high issue and one medium issue:

- HIGH: unbound injected invoice repositories with `bucket_id is None` could
  bypass the bucket equality check.
- MEDIUM: the invoice mismatch path reused the transaction-repository mismatch
  locale key.

Both were fixed before closure. The re-review reported no findings and confirmed
that no critical or high issues remain.

Validation:

- `uv run --no-sync ruff check src/aeat/application/aggregation/_renta_ledger.py src/aeat/application/aggregation/test_renta_ledger.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_renta_ledger.py` passed with 15 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Disposition: close `AFR-090`.
