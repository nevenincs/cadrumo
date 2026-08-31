---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:82f6aed9f32a7c8289d39a963a7de426fbbdb3e1eec8bcbafa40070839292a58'
step_id: 'S260'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retire the 5 counterpart_bindings re-export(s) from the registry bindings dispatch module by direct-importing CounterpartAggregationObservation, CounterpartObservationRequirement, counterpart_binding_requirements, resolve_counterpart_binding_row_values, resolve_counterpart_binding_values from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols.

## Scope

- `src/cadrumo/domain/calculations/registry/counterpart_bindings.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_counterpart_bindings.py -q -m unit` -> `pass` (19 passed)

## Notes

validate_counterpart_binding, imported from the same counterpart_bindings.py module, stays: it is a genuine dispatch-table entry for BindingSourceKind.LEDGER_TRANSACTION, not in __all__, out of this Step's named scope.
