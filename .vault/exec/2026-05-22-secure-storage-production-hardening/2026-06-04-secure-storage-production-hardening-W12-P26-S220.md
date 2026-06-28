---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S220'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W17-P37-S425]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s220-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S220`

Closed `AFR-118` for business-operation invoice storage.

## Description

- Reviewed `src/aeat/application/ledger/_business_operation_invoice.py` against
  the earlier `W17.P37.S425` JSONL-to-secure-object migration.
- Reclassified the stale AFR row from `manifest-discovery` to `runtime-default`
  because payable and collectible business-operation invoice catalogues now use
  `BusinessOperationInvoiceRepository` over `SecureBoundRepository`.
- Changed default bucket-event history construction from service-construction
  time to per-operation bucket resolution through
  `secure_object_repository_for_bucket(bucket_id, settings)`.
- Added a real runtime test proving the service works without an injected
  bucket-event repository and persists the emitted event through the active
  runtime bucket.
- Closed `S220` through `vaultspec-core vault plan step check` and aligned
  `AFR-118` to closed.

## Outcome

`AFR-118` is closed as `runtime-default`. The legacy plain-file classification
was stale after `W17.P37.S425`; the remaining event-history default now follows
the requested operation bucket instead of caching an ambient repository before a
bucket is known.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/ledger/_business_operation_invoice.py src/aeat/application/ledger/test_business_operation_invoice.py`
- `uv run --no-sync pytest -q src/aeat/application/ledger/test_business_operation_invoice.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No direct production `SecureObjectRepository` construction outside the runtime
factory, naked environment access, settings bypass, silent exception swallowing,
`noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail, or tautological test was
introduced.
