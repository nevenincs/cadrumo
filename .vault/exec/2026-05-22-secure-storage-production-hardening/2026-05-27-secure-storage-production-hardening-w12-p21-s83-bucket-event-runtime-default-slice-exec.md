---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S83'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P21.S83` Bucket Event Runtime-Default Slice

Closed the `AFR-219` bucket-event-history repository runtime-default slice without touching concurrent registry, declaration, auth, master-key, locale, or fixture worktree changes.

## Changes

- Migrated `BucketEventHistoryRepository` no-argument construction from direct `SecureObjectRepository()` creation to `secure_object_repository_for_active_bucket()`.
- Preserved explicit `objects=` injection for tests and higher-level orchestrators that already own a secure-object repository.
- Kept the existing encrypted namespace, object key, sensitivity class, envelope version, and payload schema unchanged.

## Validation

- `uv run pytest src/aeat/domain/buckets/test_event_history_roundtrip.py -q` - 2 passed.
- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_missing_session -k bucket_events src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_route_session_mismatch -k bucket_events src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_event_and_workflow_run_defaults_isolate_active_profile_writes -q` - 2 passed, 65 deselected.
- `uv run ruff check src/aeat/domain/buckets/_event_repository.py src/aeat/domain/buckets/test_event_history_roundtrip.py` - passed.
- `rg -n "SecureObjectRepository\\(" src/aeat/domain/buckets/_event_repository.py` - no remaining direct constructor hits in the repository file.

## Residual Debt

- `S83` remains open because it also owns workflow state and other runtime-default surfaces.
- The broader production direct-construction guard still reports unrelated direct `SecureObjectRepository` defaults outside this slice.
- `usage_ratios` remains a separate semantic routing decision because that API takes an explicit `bucket_id` and existing tests currently exercise multiple logical bucket ids inside one active runtime.

## Tracking

Completed internal tasklist for this slice:

- Select clean domain runtime-default target: complete.
- Migrate bucket-event default repository construction to runtime-owned factory: complete.
- Verify missing-session refusal, route-mismatch refusal, active-profile isolation, and encrypted roundtrip: complete.
- Complete focused code review: complete.
- Persist slice evidence: complete.
