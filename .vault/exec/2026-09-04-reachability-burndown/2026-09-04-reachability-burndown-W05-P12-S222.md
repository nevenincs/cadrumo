---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:f17934287b1c4174de4f4e316ef34a48d361d42a8834379a42926beb2ec7e2a1'
step_id: 'S222'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the development/test-only registry snapshot-coordinate production module, its unused RegistrySnapshotId alias and facade exports, and the orphaned helper/census test; construct the report-only four-coordinate string at the development parity and test-scenario owners without preserving a shipped canonicalization seam or named emitter inventory, and correct the stale identifier reference.

## Scope

- `Registry snapshot-coordinate module and orphan test`
- `core identity alias/facade`
- `development parity report`
- `registry scenario test support`
- `canonical-identifier reference`
- `exact reachability signal`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `.vault/reference/2026-08-07-canonical-identifiers-reference.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `dev/registry/parity/_workbook_parity.py`
- `M` `src/cadrumo/core/identity/__init__.py`
- `M` `src/cadrumo/core/identity/_namespace.py`
- `D` `src/cadrumo/domain/calculations/registry/snapshot_coordinate.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/_scenarios.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_snapshot_coordinate.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S222.md`
- `verify:` `rg -n "RegistrySnapshotId|snapshot_coordinate|registry_snapshot_id_for|registry_snapshot_id\\(" src/cadrumo dev --glob '*.py'` -> `pass (no matches)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/identity/_namespace.py src/cadrumo/core/identity/__init__.py dev/registry/parity/_workbook_parity.py src/cadrumo/domain/calculations/registry/tests/_scenarios.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s222 src/cadrumo/domain/calculations/registry/tests/test_registry_scenarios.py dev/registry/parity/tests` -> `pass (19 passed)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 60 unreachable modules, 308 exact unused symbols, 11 orphaned tests, 2029/2090 shipped modules reachable)`
