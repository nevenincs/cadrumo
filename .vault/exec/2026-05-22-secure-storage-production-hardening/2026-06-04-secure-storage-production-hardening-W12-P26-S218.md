---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S218'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s218-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S218`

Closed `AFR-116` for the invoice catalogue source resolver.

## Description

- Reviewed `src/aeat/application/invoices/_source_resolver.py` against the
  source-mesh runtime repository contract.
- Corrected the plan target from `manifest-discovery` to `runtime-default`
  because the resolver loads the encrypted invoice catalogue when a revision
  owns invoice sources.
- Passed `context.bucket_id` into the default `InvoiceCatalogueRepository`
  construction so the context bucket remains authoritative.
- Added a real two-bucket runtime regression proving a mismatched context bucket
  fails closed at the storage runtime boundary instead of silently resolving
  against the ambient active profile.
- Closed `S218` through `vaultspec-core vault plan step check` and aligned
  `AFR-116` to closed.

## Outcome

`AFR-116` is closed as `runtime-default`. The source resolver now binds its
production repository to the calculation context bucket and keeps injected
repositories available for explicit tests or caller-owned composition.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/invoices/_source_resolver.py src/aeat/application/invoices/test_source_resolver.py`
- `uv run --no-sync pytest -q src/aeat/application/invoices/test_source_resolver.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No direct production `SecureObjectRepository` construction, naked environment
access, settings bypass, silent exception swallowing, `noqa`, `pragma`,
monkeypatch, fake, mock, skip, xfail, or tautological test was introduced.
