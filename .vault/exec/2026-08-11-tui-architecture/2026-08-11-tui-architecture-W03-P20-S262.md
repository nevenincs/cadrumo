---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:efc82b732bd4b8cbeb64bc74126ba2ea3816798e26997e59cd9c898f77942951'
step_id: 'S262'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retire the 2 donativo_bindings re-export(s) from the registry bindings dispatch module by direct-importing DonativoDonorObservation, resolve_donativo_binding_row_values from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols.

## Scope

- `src/cadrumo/domain/calculations/registry/donativo_bindings.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_detail_row_field_declaration_coverage.py src/cadrumo/application/calculations/tests/test_row_set_assembly.py src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py -q -m unit` -> `pass` (88 passed)

## Notes

validate_donativo_binding stays: DONATIVO_DONOR dispatch-table entry, never in __all__, out of this Step's named scope.
