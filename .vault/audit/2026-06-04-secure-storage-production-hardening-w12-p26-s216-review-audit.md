---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S216]]'
---

# `secure-storage-production-hardening` `W12.P26.S216` Review

## S216-001 | PASS | Invoice queries read through runtime repositories

Repository-backed invoice query helpers load `InvoiceCatalogueRepository`, and
link verification loads both invoice and transaction catalogues from their
runtime-backed repositories. The module does not read plaintext invoice stores,
derive SQL routes, inspect active sessions, or access environment variables.

## S216-002 | FIXED | Link verification binds both catalogues to the requested bucket

`verify_invoice_repository_links(bucket_id=...)` already passed the requested
bucket to `TransactionCatalogueRepository`, but the invoice repository defaulted
through active-bucket resolution. It now passes the same `bucket_id` to
`InvoiceCatalogueRepository`, and a real isolated-runtime test covers the
repository-backed query path.

## S216-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/invoices/_queries.py src/aeat/application/invoices/test_queries.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/invoices/test_queries.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for S216.

Disposition: close `AFR-114` as `runtime-default`.
