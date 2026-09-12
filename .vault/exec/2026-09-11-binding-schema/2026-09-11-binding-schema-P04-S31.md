---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:b07306ed4dab33bc5a4f3ae8a66ff18051ba8672aa58cbda918a4b8ce2ab2776'
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

- `M` `src/cadrumo/domain/calculations/registry/ids.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_exports.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_verification.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_surfaces.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `A` `dev/registry/author_family_identities.py`
- `A` `dev/registry/tests/test_author_family_identities.py`
- `M` `dev/registry/tests/test_export_projection_refs.py`
- `M` `dev/registry/tests/test_registry_schema_part3.py`
- `M` `dev/registry/tests/test_referential_integrity_part1.py`
- `M` `dev/registry/pipeline/test_export_tree.py`
- `M` `src/cadrumo/application/modelo/tests/test_actions.py`
- `M` `src/cadrumo/application/modelo/tests/test_verification_substance.py`
- `M` `src/cadrumo/application/modelo/tests/test_verification_substance_advisory.py`
- `M` `src/cadrumo/application/modelo/tests/test_modelo_100_settlement_completeness_advisory.py`
- `M` `src/cadrumo/application/modelo/tests/test_modelo_131_modulos_computed_diverges_advisory.py`
- `M` `src/cadrumo/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/{200,296,303}/revisions/*/projection_endpoints/*.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/{100,111,115,123,130,131,151,180,190,193,200,202,210,216,296,303,309,322,349}/revisions/*/verification_predicates/*.toml`
- `verify:` `uv run --no-sync python -m pytest dev/registry/tests/test_author_family_identities.py -q -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.registry.analysis.edition_delta_status --lines --totals-only` -> `pass`

## Notes

Modelos 353 and 390 were held by an in-flight span replay and left deferred by
this pass; their sixteen predicate ids were authored by a concurrent writer in
the same derivation format before the run closed, so the corpus carries no
member without an identity. The compiler-side duplicate-projection-reference
branch in `dev/registry/compiler/validate_projection_endpoints.py` is now
unreachable through a constructed revision, because the revision boundary
refuses the duplicate first; its assertion was dropped from the owning test and
the branch itself was left to its owner. `dev/registry/compiler/_loader_internals.py`
was not edited: the two `_KEYED_FAMILIES` entries enrolling these families are
reported to that file's owner instead.
