---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:9bf164fa8647ea5c0d4ec4cf2ce777f2012fb6d5775bae40ec76f8069e569fa7'
step_id: 'S257'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retire the 2 binding_aggregation re-export(s) from the registry bindings dispatch module by direct-importing binding_aggregation_op, default_binding_aggregation_op from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols.

## Scope

- `src/cadrumo/domain/calculations/registry/binding_aggregation.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `verify:` `uv run --no-sync pytest --collect-only -q` -> `pass` (15 errors, pre-existing, none in registry/)
