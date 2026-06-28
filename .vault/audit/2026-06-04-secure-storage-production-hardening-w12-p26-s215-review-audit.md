---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S215]]'
---

# `secure-storage-production-hardening` `W12.P26.S215` Review

## S215-001 | PASS | Repository linking binds both catalogues to the requested bucket

`link_invoice_transaction_repositories()` now constructs
`InvoiceCatalogueRepository(bucket_id=bucket_id)` and
`TransactionCatalogueRepository(bucket_id=bucket_id)` when explicit
repositories are not injected. This removes the previous ambient active-profile
dependency on the invoice side and prevents invoice/transaction catalogue
updates from drifting across profile buckets.

## S215-002 | PASS | Runtime storage roundtrip covers the fix

The focused test creates a real isolated runtime profile, persists both
catalogues through their secure repositories, links by the uppercase
transaction id, and reloads both catalogues from encrypted storage to verify
the bidirectional link.

## S215-003 | PASS | Link refusals are localized

The missing-transaction path and defensive post-link invoice lookup path now
raise `InvoiceLinkError` with `translated_message` keys and structured context.
The missing-transaction test asserts the key and context directly.

## S215-004 | PASS | Validation

- `uv run --no-sync -q ruff check src/aeat/application/invoices/_linking.py src/aeat/application/invoices/test_linking.py` passed.
- `uv run --no-sync -q pytest -q src/aeat/application/invoices/test_linking.py` passed with 3 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low storage-routing findings
remain for the S215 slice.

Disposition: close `AFR-113` as `runtime-default`.
