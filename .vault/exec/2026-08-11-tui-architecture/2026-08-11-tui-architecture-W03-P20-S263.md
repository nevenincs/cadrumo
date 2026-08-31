---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5bf0565ba3ca2b99a0ff501f68b0c27e0927dc5bb3cc607f8227b53f1b51e535'
step_id: 'S263'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retire the 3 gasto193_bindings re-export(s) from the registry bindings dispatch module by direct-importing Gasto193Observation, resolve_gasto193_binding_row_values, resolve_gasto193_binding_values from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols.

## Scope

- `src/cadrumo/domain/calculations/registry/gasto193_bindings.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_row_set_assembly.py -q -m unit` -> `pass`

## Notes

_Gasto193Selector and validate_gasto193_binding_selector_shape stay: GASTO193_CONTRIBUTOR dispatch-table entries, never in __all__, out of this Step's named scope. Definer confirmed via vaultspec-rag search before editing (query in commit message).
