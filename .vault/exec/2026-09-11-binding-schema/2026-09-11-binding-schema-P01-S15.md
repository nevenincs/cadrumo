---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-11'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:0c321c9dea03a3f16598e20208967844cbe0bad65f2b2e41e89f287b1a8d755c'
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

## Notes

- The two per-family sections were later replaced by one `identifier_evolutions` chain-family section whose members carry `family`; `binding_evolutions` and `formula_evolutions` were deleted with zero fragments authored.
- `M` `src/cadrumo/domain/calculations/registry/identifier_evolutions.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_identifier_evolutions.py`
