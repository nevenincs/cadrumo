---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:3395e5ac3ca3e5c46254242d42ae2ea9afe61d90adfcfb3ca07550bfccb46843'
step_id: 'S258'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retire the 4 bindings_previous_filing re-export(s) from the registry bindings dispatch module by direct-importing previous_filing_binding_source_casilla_ids, previous_filing_observation_requirements, previous_filing_source_reference, resolve_previous_filing_binding_values from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols.

## Scope

- `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `M` `src/cadrumo/application/registry/__init__.py`
- `verify:` `uv run --no-sync pytest --collect-only -q` -> `pass` (15 errors, pre-existing, none in registry/)

## Notes

`previous_filing_source_reference` has a genuine internal caller inside bindings.py's own PREVIOUS_FILING dispatch (binding_source_casilla_ids, binding_source_modelo), so the import stays but under a private alias (`_previous_filing_source_reference`) since a bare import still resolves as a public module attribute regardless of __all__. bindings.py retains a genuine dispatch role over PreviousModeloSelector and validate_previous_filing_binding for this source kind.
