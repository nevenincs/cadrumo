---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S26'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Replace the three private secure-objects-for-bucket route helpers with the canonical secure_object_repository_for_bucket wrapper

## Scope

- `src/aeat/domain/invoices/_repository.py`

## Description

- Promote `secure_object_repository_for_bucket` to the storage package `__all__`.
- Replace the three private `_secure_objects_for_bucket` helpers (invoices,
  transactions, user_profile) that re-derived the route via
  `inspect_bucket_storage_runtime(...).secure_object_repository()` with delegation
  to the canonical `secure_object_repository_for_bucket`.

## Outcome

Route policy now lives in one place; a future readiness/route change reaches all
three consumers. No data-exposure change (same substrate). 146 tests + smoke green.
Committed in `c22f87dbc`.

## Notes

The Axis-1 audit flagged this as enrollment-consistency (MEDIUM), explicitly not a
data-exposure bug; confirmed.
