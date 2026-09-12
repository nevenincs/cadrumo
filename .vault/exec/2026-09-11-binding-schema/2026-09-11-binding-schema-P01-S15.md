---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:f87dd10539773f0ee6fbaf3104c353bddc0a6001a5bee837c4721517c06ddf29'
step_id: 'S15'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Enrol binding_evolutions and formula_evolutions sections on ModeloRevision through a family-agnostic IdentifierEvolution union and teach section derivation to accept closed unions

## Scope

- `src/cadrumo/domain/calculations/registry/identifier_evolutions.py`
- `src/cadrumo/domain/calculations/registry/schema.py`
- `src/cadrumo/domain/calculations/registry/schema_base.py`
- `dev/registry/compiler/loader_grammar.py`
- `dev/registry/conformance/schema_family_support.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/identifier_evolutions.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_identifier_evolutions.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_base.py`
- `M` `dev/registry/compiler/loader_grammar.py`
- `M` `dev/registry/conformance/schema_family_support.py`
- `verify:` `uv run pytest dev/registry/tests/test_revision_inherited_reference_resolution.py dev/registry/tests/test_applicability_fragment_family.py src/cadrumo/domain/calculations/registry/tests/test_identifier_evolutions.py -n 0` -> `pass`
