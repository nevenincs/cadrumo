---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:9014a6e35896fac7bce7001099f318b7b10a040bbfc882297a573f64cc7b282c'
step_id: 'S190'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the three test-only inventory persistence convenience facades create_inventory_ledger, load_inventory, and save_inventory; migrate their tests and shared runtime-storage proofs to the canonical InventoryLedgerRepository owner while retaining the live application inventory service, aggregation resolver, secure namespace, and repository behavior.

## Scope

- `Inventory persistence facade and tests`
- `shared runtime-attached repository fixtures`
- `canonical repository ownership`
- `exact reachability signal`
- `focused gates`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/adapters/persistence/profile/inventory.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_inventory.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_inventory_actividad_year_uniqueness.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/_runtime_attached_repositories_support.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_runtime_attached_repositories_part1.py`
- `M` `src/cadrumo/domain/contribuyente/inventory/records.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/profile/inventory.py src/cadrumo/adapters/persistence/profile/tests/test_inventory.py src/cadrumo/adapters/persistence/profile/tests/test_inventory_actividad_year_uniqueness.py src/cadrumo/adapters/persistence/storage/tests/_runtime_attached_repositories_support.py src/cadrumo/adapters/persistence/storage/tests/test_runtime_attached_repositories_part1.py src/cadrumo/domain/contribuyente/inventory/records.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/adapters/persistence/profile/tests/test_inventory.py src/cadrumo/adapters/persistence/profile/tests/test_inventory_actividad_year_uniqueness.py src/cadrumo/domain/contribuyente/inventory/tests/test_closing_authority.py src/cadrumo/adapters/persistence/storage/tests/test_runtime_attached_repositories_part1.py::test_current_runtime_defaults_refuse_missing_session src/cadrumo/adapters/persistence/storage/tests/test_runtime_attached_repositories_part1.py::test_current_runtime_defaults_refuse_route_session_mismatch src/cadrumo/adapters/persistence/storage/tests/test_runtime_attached_repositories_part1.py::test_adapter_repository_defaults_isolate_active_profile_writes` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail`

## Notes

- The exact detector reports 338 unused symbols and 18 orphan test modules, down from 341 and 18 before S190; no baseline, threshold, or disposition list changed.
- The broader runtime-attached repository file has four peer-owned failures in workflow-envelope validation, verification-report registry provenance, M303 carry ingress provenance, and borrador snapshot registry provenance. The three inventory-owning cases pass in the focused command above.
