---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5068904f7c1d09b7ff0147b03fa0b7108d31e52354951a07230c4f70179d1764'
step_id: 'S264'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retire the 2 inventory_bindings re-export(s) from the registry bindings dispatch module by direct-importing InventoryProjectionOperation, InventorySelector from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols.

## Scope

- `src/cadrumo/domain/calculations/registry/inventory_bindings.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_inventory_binding_registry_data.py src/cadrumo/domain/calculations/registry/tests/test_inventory_casilla_binding_linkage.py src/cadrumo/application/aggregation/tests/test_inventory_source.py src/cadrumo/domain/calculations/registry/tests/test_inventory_selector.py -q -m unit` -> `pass` (51 passed)

## Notes

InventorySelector kept as a private alias (_InventorySelector) for the INVENTORY dispatch-table entry. validate_inventory_binding, same module, never in __all__, untouched. Definer confirmed via vaultspec-rag search before editing (query in commit message).
