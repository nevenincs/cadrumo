---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S86'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P21.S86` Profile Ledger Runtime-Default Slice

Closed the profile asset, amortization, and inventory ledger constructor-default slice without touching concurrent registry, aggregation, transaction, CLI, plan, or fixture changes in the shared worktree.

## Changes

- Migrated `AssetsLedgerRepository` no-argument construction to `secure_object_repository_for_active_bucket()`.
- Migrated `AmortizacionLedgerRepository` no-argument construction to `secure_object_repository_for_active_bucket()`.
- Migrated `InventoryLedgerRepository` no-argument construction to `secure_object_repository_for_active_bucket()`.
- Added explicit `objects=` injection to the asset and amortization repositories, matching the existing inventory seam.
- Preserved all secure-object namespaces, object keys, sensitivity classes, schema versions, and payload models.

## Validation

- `uv run pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_missing_session -k "profile_assets or profile_inventory or profile_amortizacion" src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_migrated_runtime_defaults_refuse_route_session_mismatch -k "profile_assets or profile_inventory or profile_amortizacion" src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_profile_asset_defaults_isolate_active_profile_writes src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py::test_adapter_repository_defaults_isolate_active_profile_writes -q` - 6 passed, 62 deselected.
- `uv run ruff check src/aeat/adapters/persistence/profile/assets.py src/aeat/adapters/persistence/profile/inventory.py` - passed.
- `rg -n "SecureObjectRepository\\(" src/aeat/adapters/persistence/profile/assets.py src/aeat/adapters/persistence/profile/inventory.py` - no remaining direct constructor hits.

## Residual Debt

- The plan still classifies the asset ledger row with remote-mirror concerns and the inventory row with retired concerns; this slice only closes the direct secure-object constructor default.
- Broader W12 direct-construction inventory still contains diagnostics, repair, modelo reconcile, live snapshot, auth diagnostics, usage-ratio, and secure-envelope factory surfaces.
- The vault plan check still fails on pre-existing duplicate `P14` and `S56`-`S61` identifiers under W07/W08; this is metadata debt, not a blocker for this implementation slice.

## Tracking

Completed internal tasklist for this slice:

- Select clean profile-ledger direct-construction target: complete.
- Route profile asset, amortization, and inventory defaults through active storage runtime: complete.
- Preserve or add explicit repository injection seams: complete.
- Verify missing-session refusal, route-mismatch refusal, active-profile isolation, and lint: complete.
- Complete focused code review: complete.
