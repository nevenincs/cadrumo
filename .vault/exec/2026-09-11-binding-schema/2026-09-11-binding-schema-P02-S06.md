---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:5d2b1adcec08c0b15b63706c4738988bd1c806e049e50457ca7ca32a968e35bb'
step_id: 'S06'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Define RelationPrefillProvider carrying relation_kind, dependency_role, source modelo, casillas and one temporal member; delete RelationDefinition, RelationRevisionSelector, RelationPeriodAlignment and the relation loader section

## Scope

- `src/cadrumo/domain/calculations/registry/schema_surfaces.py`
- `src/cadrumo/domain/calculations/registry/schema.py`
- `dev/registry/compiler/_validate_dependency_sections.py`
- `dev/registry/compiler/loader_grammar.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/relation_prefill_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_temporal.py`
- `M` `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_surfaces.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_revision_members.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_formula.py`
- `M` `src/cadrumo/domain/calculations/registry/runtime_graph.py`
- `D` `src/cadrumo/domain/calculations/registry/relation_aggregation.py`
- `A` `dev/registry/absorb_relations_into_bindings.py`
- `A` `dev/registry/generated/relation_binding_join.json`
- `D` `dev/registry/compiler/validate_relation_sources.py`
- `D` `dev/registry/compiler/validate_relation_periods.py`
- `M` `dev/registry/compiler/_validate_dependency_sections.py`
- `M` `dev/registry/compiler/_loader_revision_fragments.py`
- `M` `dev/registry/compiler/validate_constructs.py`
- `M` `dev/registry/conformance/coverage.py`
- `M` `dev/registry/edition_round_trip.py`
- `D` `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/relations/`
- `M` `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/bindings/*.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/formulas/*.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/constructs/*.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/dependency_classifications/*.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/revision.toml`
- `M` `src/cadrumo/_data/registry/authority/authority.json`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_binding_temporal_offset_by_target_period.py`
- `A` `dev/registry/tests/test_absorb_relations_into_bindings.py`
- `D` `dev/registry/tests/test_relation_closure.py`
- `D` `dev/registry/tests/test_relation_consistency.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_relation_offset.py`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline publish-authority` -> `pass`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_absorb_relations_into_bindings.py -n 0` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_binding_temporal_offset_by_target_period.py -n 0` -> `pass`

## Notes

The working-tree copy of `dev/registry/compiler/_validate_dependency_sections.py` was deleted
while retiring the relation validators; it also hosted the surviving dependency-classification
and filing-schedule validators. A concurrent contributor's committed version was restored in
its place, so any uncommitted edit that copy carried at that moment is lost.
