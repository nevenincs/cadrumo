---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:2aad32f6b38936b079d8eb8d3829141f28a8aacc930152b19676ae67d5810603'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# `binding-schema` `P02` summary

## Changes

- A `dev/registry/absorb_relations_into_bindings.py`
- A `dev/registry/generated/relation_binding_join.json`
- A `dev/registry/tests/test_absorb_relations_into_bindings.py`
- A `src/cadrumo/adapters/persistence/profile/calculation_revision_override_migration.py`
- A `src/cadrumo/adapters/persistence/profile/relation_binding_join.json`
- A `src/cadrumo/adapters/persistence/profile/relation_binding_join.py`
- A `src/cadrumo/adapters/persistence/profile/tests/test_calculation_revision_override_migration.py`
- A `src/cadrumo/application/calculations/tests/test_relation_prefill_absorbed_provider.py`
- A `src/cadrumo/application/modelo/tests/test_orphaned_override_diagnostic.py`
- A `src/cadrumo/domain/calculations/registry/tests/test_binding_temporal_offset_by_target_period.py`
- D `dev/registry/compiler/validate_relation_periods.py`
- D `dev/registry/compiler/validate_relation_sources.py`
- D `dev/registry/tests/test_relation_closure.py`
- D `dev/registry/tests/test_relation_consistency.py`
- D `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/relations/`
- D `src/cadrumo/domain/calculations/registry/relation_aggregation.py`
- D `src/cadrumo/domain/calculations/registry/tests/test_relation_handoff_paths.py`
- D `src/cadrumo/domain/calculations/registry/tests/test_relation_offset.py`
- M `dev/registry/compiler/_loader_revision_fragments.py`
- M `dev/registry/compiler/_validate_dependency_sections.py`
- M `dev/registry/compiler/validate_constructs.py`
- M `dev/registry/conformance/coverage.py`
- M `dev/registry/edition_round_trip.py`
- M `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/bindings/*.toml`
- M `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/constructs/*.toml`
- M `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/dependency_classifications/*.toml`
- M `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/formulas/*.toml`
- M `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/revision.toml`
- M `src/cadrumo/_data/registry/authority/authority.json`
- M `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`
- M `src/cadrumo/application/aggregation/m303_arrivals.py`
- M `src/cadrumo/application/aggregation/source_mesh.py`
- M `src/cadrumo/application/calculations/binding_prefill.py`
- M `src/cadrumo/application/calculations/relation_prefill.py`
- M `src/cadrumo/application/filing/draft_construction.py`
- M `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- M `src/cadrumo/application/modelo/_calculation_preparation.py`
- M `src/cadrumo/application/modelo/_calculation_source_staging.py`
- M `src/cadrumo/application/modelo/_m349_ledger_guard.py`
- M `src/cadrumo/application/modelo/_revision_replay_inputs.py`
- M `src/cadrumo/application/modelo/_work_review_assembly.py`
- M `src/cadrumo/application/modelo/calculate_input.py`
- M `src/cadrumo/application/modelo/calculation_actions.py`
- M `src/cadrumo/application/modelo/verification_cross_period.py`
- M `src/cadrumo/application/modelo/workspace.py`
- M `src/cadrumo/application/storage/calc_sheets/engine.py`
- M `src/cadrumo/application/storage/calc_sheets/layout.py`
- M `src/cadrumo/application/storage/calc_sheets/parity_harness.py`
- M `src/cadrumo/core/aggregation.py`
- M `src/cadrumo/core/errors/registry/_application_part2.py`
- M `src/cadrumo/domain/calculations/registry/binding_targets.py`
- M `src/cadrumo/domain/calculations/registry/binding_temporal.py`
- M `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py`
- M `src/cadrumo/domain/calculations/registry/formula_runtime.py`
- M `src/cadrumo/domain/calculations/registry/handoffs.py`
- M `src/cadrumo/domain/calculations/registry/period_offset_math.py`
- M `src/cadrumo/domain/calculations/registry/queries.py`
- M `src/cadrumo/domain/calculations/registry/query_reports.py`
- M `src/cadrumo/domain/calculations/registry/record_design_coverage.py`
- M `src/cadrumo/domain/calculations/registry/reference_checker.py`
- M `src/cadrumo/domain/calculations/registry/reference_checks.py`
- M `src/cadrumo/domain/calculations/registry/relation_prefill_bindings.py`
- M `src/cadrumo/domain/calculations/registry/relations.py`
- M `src/cadrumo/domain/calculations/registry/revision_context.py`
- M `src/cadrumo/domain/calculations/registry/runtime_graph.py`
- M `src/cadrumo/domain/calculations/registry/schema.py`
- M `src/cadrumo/domain/calculations/registry/schema_formula.py`
- M `src/cadrumo/domain/calculations/registry/schema_revision_members.py`
- M `src/cadrumo/domain/calculations/registry/schema_surfaces.py`
- M `src/cadrumo/domain/calculations/registry/snapshot.py`
- M `src/cadrumo/domain/calculations/registry/static_inspection.py`
- M `src/cadrumo/domain/calculations/registry/validate_revision_identity.py`
- M `src/cadrumo/entrypoints/cli/_modelo_bindings_payloads.py`
- M `src/cadrumo/entrypoints/cli/_modelo_discovery_rendering.py`
- R `src/cadrumo/domain/calculations/registry/iva_wallet_relation_targets.py -> src/cadrumo/domain/calculations/registry/iva_wallet_carry_targets.py`
