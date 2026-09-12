---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:8ed5c9a2add52f2455d449c9e2b2a46ffe9a1bf3f8d7581c8325156ae9b1d7ff'
step_id: 'S03'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Replace DataBindingDefinition with BindingDefinition(provider=BindingProvider) and delete BindingSelector, BindingSelectorMap, BindingSelectorValue, _coerce_selector and _validate_selector_shape

## Scope

- `src/cadrumo/domain/calculations/registry/schema.py`
- `src/cadrumo/domain/calculations/registry/schema_scalars.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_scalars.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_base.py`
- `M` `src/cadrumo/domain/calculations/registry/queries.py`
- `M` `src/cadrumo/domain/calculations/registry/relations.py`
- `M` `src/cadrumo/domain/calculations/registry/snapshot.py`
- `M` `src/cadrumo/domain/calculations/registry/formula_initial_values.py`
- `M` `src/cadrumo/domain/calculations/registry/reference_sections.py`
- `M` `dev/registry/compiler/_compiled_cache.py`
- `M` `dev/registry/conformance/tests/test_catalogue_verification_coverage.py`
- `M` (rename `DataBindingDefinition` -> `BindingDefinition`) 131 modules under `src/cadrumo/` and `dev/`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/` -> `fail` (40 diagnostics; corpus-shaped tests and application consumers, enumerated in the handoff)
- `verify:` `uv run basedpyright` on the changed registry modules -> `fail` (2 pre-existing predecessor-hydration diagnostics in `schema.py`)

## Notes

The registry test suite cannot execute: a repo-global autouse fixture loads the
bundled authority artifact at setup, and the committed artifact still carries the
legacy `source`/`selector`/`typed_enum` binding shape, so all 2015 tests error at
setup. The corpus and its published artifact are converted by the later corpus
step; the new provider tests were executed directly against the module to confirm
they pass (15 assertions).

Consumers of the displaced shape were left failing on purpose, per the Step
contract: 14 application resolver sites reading `binding.selector`, three reading
`binding.typed_enum`, `application/modelo/workspace_manifest.py` importing the
deleted `selector_model_for_source`, and the previous-filing tests that construct
the retired loose temporal fields.
