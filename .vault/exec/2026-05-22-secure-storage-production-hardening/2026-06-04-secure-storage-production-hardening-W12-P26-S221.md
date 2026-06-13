---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S221'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W17-P37-S424]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s221-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S221`

Closed `AFR-119` for purchase invoice evidence storage.

## Description

- Reviewed `src/aeat/application/ledger/_evidence.py` against the earlier
  `W17.P37.S424` JSONL-to-secure-object migration.
- Reclassified the stale AFR row from `manifest-discovery` to `runtime-default`
  because purchase invoice evidence now uses `PurchaseInvoiceEvidenceRepository`
  over `SecureBoundRepository`.
- Changed default bucket-event history construction from service-construction
  time to per-operation bucket resolution through
  `secure_object_repository_for_bucket(bucket_id, settings)`.
- Added a real runtime test proving the service works without an injected
  bucket-event repository and persists the emitted event through the active
  runtime bucket.
- Closed `S221` through `vaultspec-core vault plan step check` and aligned
  `AFR-119` to closed.

## Outcome

`AFR-119` is closed as `runtime-default`. The legacy plain-file classification
was stale after `W17.P37.S424`; default evidence audit-event persistence now
resolves through the requested operation bucket instead of an ambient repository
created before bucket selection.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/ledger/_evidence.py src/aeat/application/ledger/test_evidence.py`
- `uv run --no-sync pytest -q src/aeat/application/ledger/test_evidence.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No direct production `SecureObjectRepository` construction outside the runtime
factory, naked environment access, settings bypass, silent exception swallowing,
`noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail, or tautological test was
introduced.
