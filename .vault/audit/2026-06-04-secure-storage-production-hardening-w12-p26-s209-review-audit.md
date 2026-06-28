---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S209]]'
---

# `secure-storage-production-hardening` `W12.P26.S209` Review

## S209-001 | PASS | Filing review loads transaction state through runtime storage

`compute_current_approval_basis()` delegates the default transaction catalogue
path to `TransactionCatalogueRepository(bucket_id=...).load()`. That repository
resolves secure objects through `inspect_bucket_storage_runtime(bucket_id,
load_settings())`, so filing review does not construct a raw production
`SecureObjectRepository`, route SQL directly, or read a plaintext catalogue file.

## S209-002 | PASS | Fresh transaction changes are visible to stale-review checks

The previous cached loader shape would have risked stale in-process approval
fingerprints after a transaction catalogue update. The current implementation
performs a fresh repository load for every default-basis calculation. The
focused test persists an initial catalogue through the real encrypted runtime,
approves a draft without passing a catalogue override, writes a changed
catalogue, and verifies `TRANSACTION_CATALOGUE_CHANGED` is reported.

## S209-003 | PASS | Runtime refusal and localization conventions are covered

The review path refuses unready storage runtime through
`StorageValidationError`; the migrated repository matrix also covers the
transaction repository for missing sessions and route-session mismatches.
Review-facing approval errors carry translated-message keys, and stale-reason
descriptions are rendered through the locale catalogue. Locale coverage was
audited with the mandated `python -m aeat.locales` CLI.

## S209-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/filing/_review.py src/aeat/application/filing/test_review_runtime_storage.py src/aeat/application/filing/test_review_describe_stale_reason.py` passed.
- `uv run --no-sync pytest src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_review_runtime_storage.py src/aeat/application/filing/test_review_describe_stale_reason.py -q` passed with 44 tests.
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "transactions or s85_runtime" -q` passed with 3 selected tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S209
slice.

Disposition: close `AFR-107` as `runtime-default`.
