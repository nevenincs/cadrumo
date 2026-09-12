---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:4a0f95ae6e3e98f07f8742f3e8be5deeab6b2fc063799ed594f202d546afa907'
step_id: 'S07'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Rekey RelationPrefillSourceResolver and relation queries on the binding provider instead of the relation-id join

## Scope

- `src/cadrumo/application/calculations/relation_prefill.py`
- `src/cadrumo/domain/calculations/registry/queries.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/relations.py`
- `M` `src/cadrumo/domain/calculations/registry/queries.py`
- `M` `src/cadrumo/domain/calculations/registry/query_reports.py`
- `M` `src/cadrumo/domain/calculations/registry/handoffs.py`
- `R` `src/cadrumo/domain/calculations/registry/iva_wallet_relation_targets.py -> src/cadrumo/domain/calculations/registry/iva_wallet_carry_targets.py`
- `M` `src/cadrumo/domain/calculations/registry/revision_context.py`
- `M` `src/cadrumo/domain/calculations/registry/reference_checks.py`
- `M` `src/cadrumo/domain/calculations/registry/reference_checker.py`
- `M` `src/cadrumo/domain/calculations/registry/validate_revision_identity.py`
- `M` `src/cadrumo/domain/calculations/registry/snapshot.py`
- `M` `src/cadrumo/domain/calculations/registry/static_inspection.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_targets.py`
- `M` `src/cadrumo/domain/calculations/registry/record_design_coverage.py`
- `M` `src/cadrumo/domain/calculations/registry/formula_runtime.py`
- `M` `src/cadrumo/domain/calculations/registry/period_offset_math.py`
- `M` `src/cadrumo/application/calculations/relation_prefill.py`
- `M` `src/cadrumo/application/calculations/binding_prefill.py`
- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `src/cadrumo/application/modelo/_calculation_source_staging.py`
- `M` `src/cadrumo/application/modelo/_calculation_preparation.py`
- `M` `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `M` `src/cadrumo/application/modelo/_revision_replay_inputs.py`
- `M` `src/cadrumo/application/modelo/_work_review_assembly.py`
- `M` `src/cadrumo/application/modelo/_m349_ledger_guard.py`
- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/calculate_input.py`
- `M` `src/cadrumo/application/modelo/verification_cross_period.py`
- `M` `src/cadrumo/application/filing/draft_construction.py`
- `M` `src/cadrumo/application/aggregation/m303_arrivals.py`
- `M` `src/cadrumo/application/storage/calc_sheets/layout.py`
- `M` `src/cadrumo/application/storage/calc_sheets/engine.py`
- `M` `src/cadrumo/application/storage/calc_sheets/parity_harness.py`
- `M` `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_bindings_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_discovery_rendering.py`
- `M` `src/cadrumo/core/aggregation.py`
- `A` `src/cadrumo/application/calculations/tests/test_relation_prefill_absorbed_provider.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_relation_handoff_paths.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_relation_prefill_absorbed_provider.py -n 0` -> `pass`
- `verify:` `uv run --no-sync ruff check <touched>` -> `pass`
- `verify:` `uv run --no-sync basedpyright <touched production>` -> `pass`

## Notes

The runtime fold-value channel keeps its `relation_values` / `unresolved_relation_ids` /
`relation_overrides` field names and is now keyed by the target binding id. The persisted
`CalculationRevision.relation_overrides` field and its revision-identity payload were left
untouched, so an override stored against a pre-cut relation id no longer matches a key and
stops applying until the persisted-data migration lands.

Test modules that still construct or assert the retired relation family were not migrated in
this Step and fail on import or attribute access.
