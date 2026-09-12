---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:808a48217ef5c25846fe605970dbb8bce2a6c6121059ccc8b430482c582608ae'
step_id: 'S31'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Give projection_endpoints and verification_predicates a typed, edition-free identity key at their schema boundary (never an address or year), refuse collisions rather than rename, enrol both in the keyed-family materialiser list and in identifier_evolutions dispositions so they inherit across editions, and author the ids across the corpus, driving family_without_identity from 61 to 0

## Scope

- `src/cadrumo/domain/calculations/registry/schema.py`
- `src/cadrumo/domain/calculations/registry/schema_surfaces.py`
- `src/cadrumo/domain/calculations/registry/schema_exports.py`
- `dev/registry/compiler/_loader_internals.py`
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/projection_endpoints/*.toml`
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/verification_predicates/*.toml`

## Changes
