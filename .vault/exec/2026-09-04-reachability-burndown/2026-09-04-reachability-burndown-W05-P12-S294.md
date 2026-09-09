---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:e4bef8a1bc862caf6bc0f247b0f2209b2d8df87c01d7f4a7ee0e480a9f81785c'
step_id: 'S294'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only detailed storage-inventory projection, public DTOs, and taxonomy census tests; retain the live four-area inventory through a minimal private aggregation row and preserve tree/reclaim behavior.

## Scope

- `storage management service/models/tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/application/storage_management/service.py`
- `M` `src/cadrumo/application/storage_management/models.py`
- `M` `src/cadrumo/application/storage_management/tests/test_inventory_and_tree.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "collect_storage_inventory|StorageInventoryReport|StorageInventoryRow" src dev` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/storage_management/service.py src/cadrumo/application/storage_management/models.py src/cadrumo/application/storage_management/tests/test_inventory_and_tree.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q <two live area-inventory tests>` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/storage_management/tests` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

## Notes

The package slice passed 19 tests and failed four unrelated shared-runtime cases: three reclaim tests resolved cached targets outside their per-test overridden root, and one Windows tree test attempted to unlink the active product log. The two live area-inventory tests pass in isolation. Exact reachability moved from 245 to 244 unused symbols, with 31 unreachable modules and zero orphan tests.
