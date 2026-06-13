---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S213'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s213-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S213`

Closed `AFR-111` for the inventory application service.

## Description

- Reviewed `src/aeat/application/inventory/_service.py` against the
  `runtime-default` classification for secure-object, secure-bound, and
  manifest-bucket signals.
- Verified the service builds `InventoryLedgerRepository` instances through
  `secure_object_repository_for_bucket(bucket_id, settings)` rather than raw
  SQL routes, plaintext inventory JSON, or direct environment access.
- Verified bucket event emission stays bucket-scoped through
  `BucketEventHistoryRepository` and the injected secure runtime repository.
- Localized inventory-service refusal paths for invalid valuation methods,
  duplicate actividad/year ledgers, missing actividad/year ledgers, and
  duplicate movement ids.
- Updated existing real-behavior inventory tests to assert typed
  `translated_message` keys and structured context instead of matching raw
  English strings.
- Verified the inventory-service locale keys already populated through the
  centralized locale surface and retained locale validation through
  `python -m aeat.locales audit`.

## Outcome

`AFR-111` is closed as `runtime-default`. Inventory ledger persistence remains
inside the active bucket storage runtime and the reviewed service now exposes
localized, structured application errors at its public refusal boundaries.

Validation passed:

- `uv run --no-sync -q ruff check src/aeat/application/inventory/_service.py src/aeat/application/inventory/test_inventory.py src/aeat/application/inventory/test_service.py`
- `uv run --no-sync -q pytest -q src/aeat/application/inventory/test_inventory.py src/aeat/application/inventory/test_service.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No direct production `SecureObjectRepository` construction, naked environment
access, settings bypass, silent exception swallowing, `noqa`, `pragma`,
monkeypatch, fake, mock, skip, xfail, or tautological test was introduced.
