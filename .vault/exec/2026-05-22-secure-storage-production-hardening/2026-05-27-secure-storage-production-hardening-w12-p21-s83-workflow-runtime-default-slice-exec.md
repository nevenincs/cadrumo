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



# `secure-storage-production-hardening` `W12.P21.S83` Workflow Runtime-Default Slice

Closed the workflow-state and workflow-run runtime-default slice without touching concurrent registry, auth, locale, fixture, or unrelated plan changes in the shared worktree.

## Changes

- Migrated `WorkflowStateRepository` no-argument construction to `secure_object_repository_for_active_bucket()`.
- Migrated `WorkflowRunRepository` no-argument construction to `secure_object_repository_for_active_bucket()`.
- Preserved explicit `objects=` injection for tests and service flows that already own a secure-object repository.
- Kept `workflow_state_repository()` bootstrap behavior explicit: a cold root with no active bucket pointer receives a bare `SecureObjectRepository` only through the helper, not through repository defaults.
- Refused the bootstrap exception when an explicit `aeat_database_url` is configured, so deprecated explicit SQL routing cannot revive pre-runtime workflow persistence.
- Removed the active-profile broad fallback that swallowed runtime-factory failures and reopened a default repository.
- Changed `StorageRuntime.secure_object_repository()` to use the central `get_engine(settings)` cache so runtime-created SQLite handles are released by `dispose_engine()`.

## Validation

- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_missing_session -k "workflow_state or workflow_runs" src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_route_session_mismatch -k "workflow_state or workflow_runs" src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_workflow_state_default_isolates_active_profile_writes src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_event_and_workflow_run_defaults_isolate_active_profile_writes -q` - 5 passed, 63 deselected.
- `uv run pytest src/aeat/application/workflow/test_runtime_defaults.py src/aeat/application/workflow/test_persistence.py src/aeat/application/workflow/test_run_persistence_roundtrip.py -q` - 14 passed.
- `uv run pytest src/aeat/application/test_config_reset.py -q` - 6 passed.
- `uv run ruff check src/aeat/application/workflow/_persistence.py src/aeat/application/workflow/test_runtime_defaults.py src/aeat/adapters/persistence/storage/runtime.py` - passed.
- `git diff --check` for the changed production files - passed.

## Residual Debt

- `S83` remains open because other runtime-default surfaces still contain direct `SecureObjectRepository()` construction.
- The bootstrap bare repository in `workflow_state_repository()` is intentionally retained for no-active-pointer recovery reads and should stay classified as `bootstrap-custody`.
- The vault plan check still fails on pre-existing duplicate `P14` and `S56`-`S61` identifiers under W07/W08; this is metadata debt, not a blocker for this implementation slice.

## Tracking

Completed internal tasklist for this slice:

- Reproduce workflow default readiness failures: complete.
- Route workflow state and workflow run defaults through the active storage runtime: complete.
- Preserve cold-root bootstrap recovery behavior explicitly: complete.
- Refuse explicit SQL URL routing without an active profile: complete.
- Align runtime repository engines with central disposal: complete.
- Verify runtime refusal, route mismatch, active-profile isolation, workflow persistence, config reset deletion, and lint: complete.
