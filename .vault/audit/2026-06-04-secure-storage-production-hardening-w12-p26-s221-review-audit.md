---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W17-P37-S424]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S221]]'
---

# `secure-storage-production-hardening` `W12.P26.S221` Review

## S221-001 | PASS | Legacy JSONL classification is stale

`W17.P37.S424` already migrated purchase invoice evidence persistence from
bucket-local JSONL into the `ledger_purchase_invoice_evidence` secure-object
namespace. The S221 register row was therefore corrected to `runtime-default`.

## S221-002 | FIXED | Default event history now resolves after bucket selection

`PurchaseInvoiceEvidenceService` previously created
`BucketEventHistoryRepository()` in `__init__()`, before mutating calls supplied
a bucket. The service now retains only injected repositories at construction
time; default event history resolves per mutating operation through
`secure_object_repository_for_bucket(bucket_id, settings)`.

## S221-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/ledger/_evidence.py src/aeat/application/ledger/test_evidence.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/ledger/test_evidence.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for S221.

Disposition: close `AFR-119` as `runtime-default`.
