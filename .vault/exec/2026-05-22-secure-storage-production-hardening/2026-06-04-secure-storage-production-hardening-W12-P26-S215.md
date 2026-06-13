---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S215'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s215-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S215`

Closed `AFR-113` for invoice-to-transaction linking.

## Description

- Reviewed `src/aeat/application/invoices/_linking.py` against its
  secure-object and manifest-bucket signals.
- Fixed repository-level linking so `InvoiceCatalogueRepository` is
  constructed with the requested `bucket_id`, matching the transaction
  repository and avoiding ambient active-profile drift.
- Added a real secure-runtime test that persists invoice and transaction
  catalogues in the requested bucket, links them, and reloads both sides from
  encrypted storage.
- Localized missing-transaction and post-link invoice lookup refusal paths with
  structured `InvoiceLinkError` context.
- Enrolled locale strings through `python -m aeat.locales scaffold` and
  `python -m aeat.locales set`.
- Closed the plan step through the vaultspec CLI; the row was reclassified to
  `runtime-default` because this slice fixes a secure repository binding, not
  a pure manifest-discovery exception.

## Outcome

`AFR-113` is closed as `runtime-default`. Invoice and transaction catalogues
now bind to the same requested bucket during repository-level linking, and
linking refusals expose localized, structured errors.

Validation passed:

- `uv run --no-sync -q ruff check src/aeat/application/invoices/_linking.py src/aeat/application/invoices/test_linking.py`
- `uv run --no-sync -q pytest -q src/aeat/application/invoices/test_linking.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No plaintext persistence, settings bypass, silent exception swallowing,
`noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail, or tautological test
was introduced.
