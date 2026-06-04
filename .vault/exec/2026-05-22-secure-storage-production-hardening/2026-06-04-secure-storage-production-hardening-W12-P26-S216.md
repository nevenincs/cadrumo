---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
step_id: 'S216'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s216-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S216`

Closed `AFR-114` for invoice query projections.

## Description

- Reviewed `src/aeat/application/invoices/_queries.py` against the affected
  file register and runtime repository ownership.
- Corrected the plan target from `manifest-discovery` to `runtime-default`
  because repository-backed query helpers read encrypted invoice and
  transaction catalogues through runtime-bound repositories.
- Passed the requested `bucket_id` into the invoice repository used by
  `verify_invoice_repository_links()`, matching the transaction repository
  binding.
- Added a real isolated-runtime test for repository-backed link verification.

## Outcome

`AFR-114` is closed as `runtime-default`. Link verification now reads both
catalogues from repositories bound to the requested bucket.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/invoices/_queries.py src/aeat/application/invoices/test_queries.py`
- `uv run --no-sync pytest -q src/aeat/application/invoices/test_queries.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No direct production `SecureObjectRepository` construction, naked environment
access, settings bypass, silent exception swallowing, `noqa`, `pragma`,
monkeypatch, fake, mock, skip, xfail, or tautological test was introduced.
