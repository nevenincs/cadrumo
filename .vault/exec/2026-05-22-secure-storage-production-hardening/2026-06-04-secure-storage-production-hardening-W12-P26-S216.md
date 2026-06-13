---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S216'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s216-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S216`

Closed `AFR-114` for invoice query helpers.

## Description

- Reviewed `src/aeat/application/invoices/_queries.py` against its
  secure-object and manifest-bucket signals.
- Fixed `verify_invoice_repository_links(bucket_id=...)` so both invoice and
  transaction catalogues load through repositories bound to the requested
  bucket id.
- Verified query projections remain in-memory transforms when a catalogue is
  injected and use secure repositories only at repository query boundaries.
- Ran the existing real secure-runtime query test that persists both
  catalogues and verifies no one-sided link inconsistencies are reported after
  bucket-bound reload.
- Closed the plan step through the vaultspec CLI; the row was reclassified to
  `runtime-default` because the reviewed path is a secure repository query,
  not a retained manifest-discovery exception.

## Outcome

`AFR-114` is closed as `runtime-default`. Repository-backed invoice link
verification now consistently binds both catalogues to the requested bucket.

Validation passed:

- `uv run --no-sync -q ruff check src/aeat/application/invoices/_queries.py src/aeat/application/invoices/test_queries.py`
- `uv run --no-sync -q pytest -q src/aeat/application/invoices/test_queries.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No plaintext persistence, settings bypass, silent exception swallowing,
`noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail, or tautological test
was introduced.
