---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S219'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s219-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S219`

Closed `AFR-117` for ledger application actions.

## Description

- Reviewed `src/aeat/application/ledger/_actions.py` against the
  runtime-default repository contract for transaction catalogue, invoice
  catalogue, and bucket-event history persistence.
- Added `_bucket_event_repository()` so default bucket-event history access is
  built through `secure_object_repository_for_bucket(bucket_id)` instead of the
  ambient active-bucket factory.
- Replaced every ambient `BucketEventHistoryRepository()` default in ledger
  action write/review/classification flows with the bucket-bound helper.
- Tightened one lifecycle helper parameter back to
  `TransactionCatalogueRepositoryProtocol`, matching the public service API.
- Added a real secure-runtime regression proving the default bucket-event
  repository fails closed when a command bucket is not the active unlocked
  bucket.
- Closed `S219` through `vaultspec-core vault plan step check` and aligned
  `AFR-117` to closed.

## Outcome

`AFR-117` is closed as `runtime-default`. Ledger transaction writes already
bound the transaction and invoice repositories to requested buckets; bucket
event history defaults now follow the same requested bucket and surface storage
runtime mismatches instead of falling back to ambient active-profile storage.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/ledger/_actions.py src/aeat/application/ledger/test_actions.py`
- `uv run --no-sync pytest -q src/aeat/application/ledger/test_actions.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The ledger action file still contains pre-existing raw
`TransactionValidationError` messages in several non-storage validation paths.
They are not introduced by this step and should be handled by a dedicated
localization/error-surface slice rather than hidden with `noqa`, `pragma`, or
exception swallowing.

Intersecting shared edits in `src/aeat/application/ledger/test_actions.py`
adjusted an existing IVA/base invariant expectation; those edits were preserved
because the shared worktree had already shifted around this file.
