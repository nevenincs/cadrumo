---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:716132e86f9564ae4fadf2c030e3c90e7aff91bafae2f6ff0da4e3771565827d'
step_id: 'S220'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only compatibility-lifecycle production module and its dormant pre-release/released regime, frozen-floor placeholders, persisted-format classification inventory, and synthetic policy tests; remove dependent enrollment assertions that merely census those declarations, preserve concrete schema-version refusal and real read/upgrade behavior at owning storage modules, and amend the accepted durability decisions and obsolete flip reference that prescribed the withdrawn metastate.

## Scope

- `Production compatibility-lifecycle metastate`
- `orphaned lifecycle tests`
- `dependent persisted-format census assertions`
- `concrete storage schema/secret-index behavior tests`
- `compatibility and durability ADR corpus`
- `obsolete checkpoint reference`
- `exact reachability signal`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/adr/2026-07-08-released-data-durability-adr.md`
- `M` `.vault/adr/2026-07-09-compatibility-lifecycle-adr.md`
- `M` `.vault/adr/2026-08-10-current-schema-only-purge-adr.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `.vault/reference/2026-07-10-compatibility-lifecycle-reference.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/adapters/persistence/storage/secret_store/store.py`
- `M` `src/cadrumo/adapters/persistence/storage/secret_store/tests/test_secret_index_version_gate.py`
- `M` `src/cadrumo/adapters/persistence/storage/storage_path_definitions.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_schema_lineage.py`
- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `D` `src/cadrumo/core/compatibility_lifecycle.py`
- `D` `src/cadrumo/core/tests/test_compatibility_lifecycle.py`
- `D` `src/cadrumo/core/tests/test_compatibility_lifecycle_gate.py`
- `D` `src/cadrumo/tests/test_persisted_format_enrollment.py`
- `M` `src/cadrumo/tests/test_release_config.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S220.md`
- `verify:` `rg -n "compatibility_lifecycle|COMPATIBILITY_REGIME|RELEASED_FORMAT_FLOORS|PERSISTED_FORMATS|PersistedFormatClass" src --glob '*.py'` -> `pass (no matches)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/tests/test_schema_lineage.py src/cadrumo/adapters/persistence/storage/secret_store/tests/test_secret_index_version_gate.py src/cadrumo/adapters/persistence/storage/secret_store/store.py src/cadrumo/application/modelo/workspace_models.py src/cadrumo/tests/test_release_config.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s220c src/cadrumo/adapters/persistence/storage/tests/test_schema_lineage.py src/cadrumo/adapters/persistence/storage/secret_store/tests/test_secret_index_version_gate.py` -> `pass (15 passed)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 61 unreachable modules, 311 exact unused symbols, 13 orphaned tests, 2029/2091 shipped modules reachable)`

## Notes

- The broader release-config test remains red because a peer-owned config currently supplies an extra `packages["."].component` field; this step changed only stale explanatory text and did not absorb that unrelated configuration drift.
