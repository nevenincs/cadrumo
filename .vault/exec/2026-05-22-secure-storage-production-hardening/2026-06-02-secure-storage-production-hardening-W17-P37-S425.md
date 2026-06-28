---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S425'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p24-s96-side-store-classification-exec]]'
---

# `secure-storage-production-hardening` `W17.P37.S425`

## Description

- Migrated payable and collectible business-operation invoice persistence from bucket-local JSONL to runtime-created secure-object storage.
- Added the `ledger_business_operation_invoices` namespace with financial sensitivity, bucket-local scope, and `{bucket_id}:{source_kind}` object grammar.
- Added `BusinessOperationInvoiceDocument` and `BusinessOperationInvoiceRepository` over `SecureBoundRepository`.
- Updated business-operation invoice tests to use a real `isolated_runtime_profile` and prove secure-object persistence, source-kind separation, and fail-closed behavior for non-active buckets.
- Removed the business-operation invoice JSONL entry from the reviewed production file-write allowlist.

## Changed Surface

- `src/aeat/application/ledger/_business_operation_invoice.py`
- `src/aeat/application/ledger/test_business_operation_invoice.py`
- `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- `src/aeat/adapters/persistence/storage/__init__.py`
- `src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`

## Outcome

Implemented and reviewed.

Payable and collectible business-operation invoices no longer persist as `Settings.aeat_invoices_dir / {source_kind} / {bucket_id}.jsonl`. The durable catalogue is a financial secure-object document resolved through `secure_object_repository_for_bucket(bucket_id, settings)` and keyed by bucket plus source-kind.

## Verification

- `uv run --no-sync pytest -q src/aeat/application/ledger/test_business_operation_invoice.py src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_w03_s22_auth_session_cache_remote_namespaces_are_registered src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_w03_s22_namespace_registration_coverage_is_present` passed with 41 tests.
- `uv run --no-sync ruff check src/aeat/application/ledger/_business_operation_invoice.py src/aeat/application/ledger/test_business_operation_invoice.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py` passed.
- `rg -n "aeat_invoices_dir|jsonl|write_text|read_text|storage_path\\(" src/aeat/application/ledger/_business_operation_invoice.py src/aeat/application/ledger/test_business_operation_invoice.py` found no production persistence path in `_business_operation_invoice.py`; remaining hits are the regression test name and absent-legacy-file assertion.

## Notes

The broader `test_sensitive_persistence_policy.py::test_production_file_write_inventory_is_reviewed` run is currently blocked by a separate shared-worktree `_iva_compensation_wallet.py` diagnostic write inventory delta. The S425-scoped migration removed the business-operation invoice allowlist entry and did not introduce that wallet diagnostic write.
