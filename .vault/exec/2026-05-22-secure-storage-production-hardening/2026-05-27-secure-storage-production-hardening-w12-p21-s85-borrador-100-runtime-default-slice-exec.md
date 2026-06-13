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



# `secure-storage-production-hardening` `W12.P21.S85` Borrador 100 Runtime-Default Slice

Closed the Borrador 100 snapshot repository direct-constructor slice without touching concurrent registry, ledger, calculation, scratch, fixture, or unrelated plan worktree changes.

## Changes

- Migrated `Borrador100SnapshotRepository` no-argument secure-object construction to `secure_object_repository_for_bucket(self._bucket_id)`.
- Preserved explicit `objects=` injection for unit tests and service flows that already own a secure-object repository.
- Added a route-mismatch regression test proving a repository constructed for one bucket cannot write logical rows into another active bucket's physical database.
- Kept the existing encrypted namespace, object-key layout, sensitivity class, schema version, payload model, lifecycle invariants, and bucket-id filtering unchanged.

## Validation

- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_missing_session -k borrador_100_snapshot src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_route_session_mismatch -k borrador_100_snapshot src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_s85_runtime_default_surfaces_isolate_active_profile_writes -q` - 2 passed, 65 deselected.
- `uv run pytest src/aeat/application/live/test_borrador_100_roundtrip.py::test_borrador_100_repository_default_refuses_active_bucket_mismatch src/aeat/application/live/test_borrador_100.py src/aeat/application/live/test_borrador_100_roundtrip.py -q` - 12 passed.
- `uv run ruff check src/aeat/application/live/_borrador_100.py src/aeat/application/live/test_borrador_100.py src/aeat/application/live/test_borrador_100_roundtrip.py` - passed.
- `rg -n "SecureObjectRepository\\(" src/aeat/application/live/_borrador_100.py` - no remaining direct constructor hits.

## Residual Debt

- The broader `S85` runtime-default rollout still includes application diagnostics, repair decisions, and other application-layer direct-constructor surfaces.
- The shared runtime-migration test module still has a pre-existing import-order lint finding when linted directly; this slice did not edit that file.

## Tracking

Completed internal tasklist for this slice:

- Select clean Borrador 100 direct-construction target: complete.
- Route the snapshot repository default through active storage runtime: complete.
- Preserve explicit repository injection and bucket-id validation semantics: complete.
- Prove constructor bucket mismatch refuses instead of cross-writing into the active bucket database: complete.
- Verify missing-session refusal, route-mismatch refusal, active-profile isolation, roundtrip/lifecycle behavior, and focused lint: complete.
- Complete focused code review: complete.
