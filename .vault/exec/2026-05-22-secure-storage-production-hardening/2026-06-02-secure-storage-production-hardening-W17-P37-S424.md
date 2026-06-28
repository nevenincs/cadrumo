---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S424'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p24-s96-side-store-classification-exec]]'
---

# `secure-storage-production-hardening` `W17.P37.S424`

## Description

- Migrated purchase invoice evidence persistence from bucket-local JSONL to runtime-created secure-object storage.
- Added the `ledger_purchase_invoice_evidence` namespace with financial sensitivity, bucket-local scope, and `{bucket_id}` object grammar.
- Added `PurchaseInvoiceEvidenceDocument` and `PurchaseInvoiceEvidenceRepository` over `SecureBoundRepository`.
- Updated evidence tests to use the real `isolated_runtime_profile` settings and prove no purchase-evidence JSONL file is written.
- Removed the purchase invoice evidence JSONL entry from the reviewed production file-write allowlist.

## Changed Surface

- `src/aeat/application/ledger/_evidence.py`
- `src/aeat/application/ledger/test_evidence.py`
- `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- `src/aeat/adapters/persistence/storage/__init__.py`
- `src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`

## Outcome

Implemented and reviewed.

Purchase invoice evidence no longer persists as `Settings.aeat_purchase_invoice_evidence_dir / {bucket_id}.jsonl`. The durable catalogue is a financial secure-object document resolved through `secure_object_repository_for_bucket(bucket_id, settings)`.

## Verification

- `uv run --no-sync pytest -q src/aeat/application/ledger/test_evidence.py src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_w03_s22_auth_session_cache_remote_namespaces_are_registered src/aeat/adapters/persistence/storage/test_namespace_registry.py::test_w03_s22_namespace_registration_coverage_is_present` passed with 12 tests.
- `uv run --no-sync ruff check src/aeat/application/ledger/_evidence.py src/aeat/application/ledger/test_evidence.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py` passed.
- `rg -n "aeat_purchase_invoice_evidence_dir|jsonl|write_text|read_text|storage_path\\(" src/aeat/application/ledger/_evidence.py src/aeat/application/ledger/test_evidence.py` found no production persistence path in `_evidence.py`; remaining hits are test assertions/input setup.

## Notes

The broader `test_sensitive_persistence_policy.py` run is currently blocked by a separate shared-worktree `_iva_compensation_wallet.py` diagnostic write inventory delta. The S424-scoped migration removed the purchase invoice evidence allowlist entry and did not introduce that wallet diagnostic write.
