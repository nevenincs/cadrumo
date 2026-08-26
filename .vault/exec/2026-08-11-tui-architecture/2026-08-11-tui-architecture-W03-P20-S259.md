---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a3d3cfc6f82ad9cf262ac958b7763462a5f91becde8adfe358a7624f5a611569'
step_id: 'S259'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retire the 4 core.aggregation re-export(s) from the registry bindings dispatch module by direct-importing BindingAggregationOp, CounterpartSourceKind, INVOICE_BINDING_SOURCE_KINDS, LEDGER_BINDING_SOURCE_KINDS from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols. This is a CROSS-LAYER facade: a core symbol republished through a registry module, so the direct import must reach core.

## Scope

- `src/cadrumo/core/aggregation.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `verify:` `uv run --no-sync pytest --collect-only -q` -> `pass` (15 errors, pre-existing, none in registry/)

## Notes

Zero internal use of any of the four names in bindings.py; a pure cross-layer re-export with no dispatch role. BindingSourceKind, imported from the same core.aggregation module and genuinely used throughout this module's dispatch logic, stays.
