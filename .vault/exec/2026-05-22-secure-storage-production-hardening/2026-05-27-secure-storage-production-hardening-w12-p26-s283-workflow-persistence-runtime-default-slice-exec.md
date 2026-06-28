---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S283'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P26.S283` Workflow Persistence Runtime-Default Slice

Closed `AFR-181` by removing application-layer direct secure-object construction from workflow persistence while preserving the deliberately narrow cold-root repair exception.

## Changes

- Added `secure_object_repository_for_cold_bootstrap_state` to the storage runtime repository factory module.
- Moved the no-active-pointer workflow bootstrap exception from `workflow_state_repository` into that named storage-layer factory.
- Made the bootstrap factory self-policing: it refuses explicit database routes and refuses when an active profile bucket resolves.
- Kept normal workflow state and run persistence routed through `secure_object_repository_for_active_bucket`.
- Added direct runtime tests for the cold-bootstrap factory's allowed and refused states.
- Closed the file-level plan row with `uv run vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md S283` and marked `AFR-181` as migrated in the audit register.

## Validation

- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime.py::test_cold_bootstrap_repository_is_available_before_profile_selection src/aeat/adapters/persistence/storage/test_runtime.py::test_cold_bootstrap_repository_refuses_active_profile src/aeat/adapters/persistence/storage/test_runtime.py::test_cold_bootstrap_repository_refuses_explicit_database_route src/aeat/application/workflow/test_persistence.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py -q` - 25 passed.
- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_missing_session -k workflow_state src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_route_session_mismatch -k workflow_state src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_workflow_state_default_isolates_active_profile_writes -q` - 3 passed, 64 deselected.
- `uv run ruff check src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/application/workflow/_persistence.py` - passed.
- `rg -n "SecureObjectRepository\\(" src/aeat/application/workflow/_persistence.py` - no remaining direct constructor hits.
- Focused code review re-review reported no findings.

## Residual Debt

- The runtime repository module now owns the cold-root process-default exception. The remaining direct constructors in repair diagnostics, envelope test harnesses, and the storage runtime factory require separate classification because some are intentional bootstrap, factory, or test-contract surfaces rather than application runtime defaults.

## Tracking

Completed internal tasklist for this slice:

- Identify the workflow persistence direct constructor as a cold-root repair exception: complete.
- Move the exception behind a named storage-layer factory: complete.
- Make the exception self-policing against active profiles and explicit database routes: complete.
- Preserve repair bootstrap and active-profile runtime behavior: complete.
- Verify tests, lint, constructor inventory, plan row closure, and review: complete.
