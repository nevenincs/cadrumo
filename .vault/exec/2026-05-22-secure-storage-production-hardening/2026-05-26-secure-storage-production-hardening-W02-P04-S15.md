---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S15'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
---



# `secure-storage-production-hardening` `W02.P04.S15`

Enrolled the ledger transaction and invoice catalogue repository defaults in runtime-created, bucket-attached secure storage while preserving explicit repository injection for real-behavior tests and controlled callers.

## Changes

- Added runtime-backed secure-object factories for `TransactionCatalogueRepository` and `InvoiceCatalogueRepository` default construction.
- Added `bucket_id` awareness to `InvoiceCatalogueRepository` so ledger flows can bind invoice catalogue access to the addressed bucket instead of relying on an unqualified physical store.
- Routed ledger invoice repository resolution through a bucket-aware helper and rejected injected invoice repositories that declare a conflicting bucket.
- Kept remove/reset ledger operations from opening invoice storage when no purchase-invoice evidence is involved, so no-invoice operations do not require an unnecessary invoice runtime.
- Regrounded touched repository tests on real active-bucket runtime setup through `override_settings` and `BucketSession`, removing patched environment database routing from the changed surfaces.

## Validation

- `uv run ruff check src/aeat/domain/transactions/_repository.py src/aeat/domain/invoices/_repository.py src/aeat/application/ledger/_actions.py src/aeat/domain/test_runtime_repository_enrollment.py`
- `uv run ruff check src/aeat/domain/invoices/test_reconciliation.py src/aeat/application/ledger/_actions.py src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/test_runtime_repository_enrollment.py`
- `uv run pytest src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/test_runtime_repository_enrollment.py src/aeat/domain/invoices/test_repository.py src/aeat/domain/invoices/test_secure_storage_roundtrip.py src/aeat/domain/invoices/test_reconciliation.py src/aeat/application/ledger/test_actions.py -q`
- `uv run python -m aeat.locales audit`
- `rg -n "monkeypatch|setenv\\(|AEAT_DATABASE_URL" src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/invoices/test_reconciliation.py src/aeat/domain/test_runtime_repository_enrollment.py`

## Review

The targeted direct-construction audit found no production `SecureObjectRepository()` fallback in the ledger, transaction, or invoice S15 surface. Remaining direct repository construction matches runtime-enrolled domain constructors or explicit test injection. Bucket-event repository runtime enrollment remains outside this step and is tracked by the later repository migration wave.
