---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S213]]'
---

# `secure-storage-production-hardening` `W12.P26.S213` Review

## S213-001 | PASS | Inventory persistence is runtime-bound secure storage

`InventoryService` resolves settings through `load_settings()` when no
explicit settings object is injected, then builds inventory repositories with
`secure_object_repository_for_bucket(bucket_id, settings)`. The repository
stores the inventory ledger document under the profile inventory ledger
namespace; the service does not write plaintext inventory files or derive SQL
routes directly.

## S213-002 | PASS | Bucket events remain bucket scoped

Mutating inventory verbs emit bucket events through
`BucketEventHistoryRepository` and `append_bucket_event()`. The tests exercise
the real runtime profile and verify event ids and event types for create,
movement add, valuation preview, and remove.

## S213-003 | PASS | Application refusals are localized and structured

Inventory service input and lookup refusals now carry translated-message keys
under `application.inventory.service.errors.*` with structured context for the
non-secret business identifiers involved in the refusal. Existing tests assert
those keys and contexts directly.

## S213-004 | PASS | Validation

- `uv run --no-sync -q ruff check src/aeat/application/inventory/_service.py src/aeat/application/inventory/test_inventory.py src/aeat/application/inventory/test_service.py` passed.
- `uv run --no-sync -q pytest -q src/aeat/application/inventory/test_inventory.py src/aeat/application/inventory/test_service.py` passed with 25 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low storage-routing findings
remain for the S213 slice. The raw inventory-service error-message issue found
during review was fixed in this step rather than deferred.

Disposition: close `AFR-111` as `runtime-default`.
