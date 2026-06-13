---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S216]]'
---

# `secure-storage-production-hardening` `W12.P26.S216` Review

## S216-001 | PASS | Link consistency queries use the requested bucket

`verify_invoice_repository_links(bucket_id=...)` now constructs
`InvoiceCatalogueRepository(bucket_id=bucket_id)` and
`TransactionCatalogueRepository(bucket_id=bucket_id)`. This removes the
previous invoice-side ambient active-profile dependency from the repository
query path.

## S216-002 | PASS | Projection helpers remain storage-free

`list_invoice_rows()` and `list_unmatched_invoice_rows()` operate on supplied
`InvoiceCatalogue` instances. They perform deterministic projections and do
not open files, inspect manifests, or construct repositories.

## S216-003 | PASS | Runtime test covers the repository boundary

The existing repository query test uses a real isolated runtime profile,
persists both catalogues through secure repositories, and verifies consistency
after reloading through the bucket-bound repository query.

## S216-004 | PASS | Validation

- `uv run --no-sync -q ruff check src/aeat/application/invoices/_queries.py src/aeat/application/invoices/test_queries.py` passed.
- `uv run --no-sync -q pytest -q src/aeat/application/invoices/test_queries.py` passed with 4 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low storage-routing findings
remain for the S216 slice.

Disposition: close `AFR-114` as `runtime-default`.
