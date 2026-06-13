---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S85'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P21.S85` Auth Diagnostics Runtime-Default Slice

Closed the encrypted auth diagnostics direct-constructor slice without touching concurrent registry, ledger, calculation, scratch, or unrelated plan worktree changes.

## Changes

- Migrated auth diagnostic list, detail load, and operator phone-state update paths from direct `SecureObjectRepository()` construction to `secure_object_repository_for_active_bucket()`.
- Kept the existing encrypted namespace, object keys, sensitivity class, schema version, payload shape, URL redaction, and fingerprint redaction unchanged.
- Reused one runtime-owned repository inside the phone-state update so the load and save are routed through the same active bucket.

## Validation

- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_missing_session -k auth_diagnostics src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_route_session_mismatch -k auth_diagnostics src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_s85_runtime_default_surfaces_isolate_active_profile_writes -q` - 2 passed, 65 deselected.
- `uv run ruff check src/aeat/application/auth/_diagnostics.py` - passed.
- `rg -n "SecureObjectRepository\\(" src/aeat/application/auth/_diagnostics.py` - no remaining direct constructor hits.

## Residual Debt

- The broader `S85` runtime-default rollout still includes application diagnostics, repair decisions, and live snapshot surfaces.
- A focused ruff run that included the large shared runtime-migration test file reported a pre-existing import-order issue in that test module; this slice did not edit the file.

## Tracking

Completed internal tasklist for this slice:

- Select clean auth diagnostics direct-construction target: complete.
- Route list, detail, and phone-state update paths through active storage runtime: complete.
- Verify missing-session refusal, route-mismatch refusal, active-profile isolation, and focused lint: complete.
- Complete focused code review: complete.
