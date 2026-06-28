---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S169'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P26.S169` Secure-Bound Repository Runtime-Default Slice

Closed `AFR-067` by routing no-argument `SecureBoundRepository` construction through the runtime-owned secure-object repository factory and removing the broad active-bucket fallback.

## Changes

- Added `secure_object_repository_for_active_bucket_or_default_route` as the named storage-layer boundary for active-bucket-or-process-default repository construction.
- Made the helper derive active-bucket selection from supplied `Settings` before consulting the process pointer, so settings-scoped active profiles fail closed too.
- Updated `_secure_repository.py` to call the runtime helper directly instead of catching all exceptions and falling back to a process-default repository.
- Added regression coverage for active-profile construction without an active bucket session.
- Removed touched `type: ignore` suppressions by casting the dynamic Pydantic envelope boundary explicitly.
- Hardened cold-bootstrap routing so settings-scoped active-bucket routes are refused, matching the process-global active-profile guard.
- Kept `tr()` localized errors with explicit locale threading in the storage runtime factory helpers.

## Validation

- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository_contract.py -q` - 28 passed.
- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "submission or justificante or filing_drafts or filing_amendments" -q` - 8 passed, 69 deselected.
- `uv run ruff check src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/persistence/storage/envelope/_secure_repository.py src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py` - passed.
- `rg -n "except Exception|noqa|pragma|type: ignore|SecureObjectRepository\\("` over the touched secure-bound/runtime files - only explicit engine test injection and centralized runtime factory constructors remain.
- Focused code review initially found one settings-scoped bypass; after the fix and regression tests, re-review reported no findings.

## Residual Debt

- The no-active process-default route remains intentionally available for explicit harness and bootstrap-adjacent code. Once an active bucket is selected, route and session failures now surface through the runtime readiness path.

## Tracking

Completed internal tasklist for this slice:

- Remove broad exception swallowing from secure-bound default construction: complete.
- Centralize active-bucket/default route selection in the storage runtime factory module: complete.
- Fail closed for process-global and settings-scoped active profiles: complete.
- Keep localized error handling and remove touched suppressions: complete.
- Verify tests, lint, constructor inventory, plan row closure, and review: complete.
