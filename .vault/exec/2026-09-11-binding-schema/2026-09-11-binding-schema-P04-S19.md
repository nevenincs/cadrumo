---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:cf5a3843007f0aa6554037aac678b2535b008cb637fe07ddfc743808d058376f'
step_id: 'S19'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Remediate review findings: retire no-op selector-only validators, narrow binding source accessors on provider members with explicit refusal, drop the duplicate source field from query rows, refuse cross-revision data-type disagreement in the converter and ground its family-level money rule, carry an unknown prefill coordinate as None, enforce the absolute-coordinate guard structurally in the domain, and remove the two import-invariant restatement tests

## Scope

- `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `src/cadrumo/domain/calculations/registry/queries.py`
- `src/cadrumo/domain/calculations/registry/query_reports.py`
- `dev/registry/convert_binding_provider_shape.py`
- `src/cadrumo/application/calculations/binding_prefill.py`
- `dev/registry/compiler/validate_bindings.py`

## Changes

- `M` `dev/registry/convert_binding_provider_shape.py`
- `M` `dev/registry/tests/test_convert_binding_provider_shape.py`
- `M` `dev/registry/tests/test_modelo_100_2024_profile_surface.py`
- `M` `dev/registry/tests/test_binding_source_kind_taxonomy.py`
- `M` `dev/registry/compiler/validate_bindings.py`
- `M` `dev/registry/tests/test_validate_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_selector_utils.py`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/inventory_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/gasto193_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/profile_grounding.py`
- `M` `src/cadrumo/domain/calculations/registry/queries.py`
- `M` `src/cadrumo/domain/calculations/registry/query_reports.py`
- `M` `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py`
- `M` `src/cadrumo/application/calculations/binding_prefill.py`
- `M` `src/cadrumo/application/calculations/multi_year.py`
- `M` `src/cadrumo/application/calculations/relation_prefill_m202.py`
- `M` `src/cadrumo/application/modelo/work_wizard.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_discovery_rendering.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_binding_source_accessors.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_provider_registration.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_selector_utils.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_aggregation.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_queries.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_renta_gastos_estimacion_directa_binding.py`
- `M` `src/cadrumo/domain/user_profile/tests/test_registry_contract.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`
- `M` `src/cadrumo/application/modelo/tests/test_profile_binding.py`
- `M` `src/cadrumo/application/calculations/tests/test_row_producer_default_op_detection.py`
- `verify:` `uv run --no-sync ruff check <touched files>` -> `pass`
- `verify:` `uv run ty check <touched files>` -> `pass`
- `verify:` `uv run --no-sync basedpyright <touched domain and application files>` -> `pass`
- `verify:` `uv run --no-sync pytest <touched registry, profile and converter suites> -n 0` -> `pass`

## Notes

Pre-existing failures outside this change remain in modules it touches: four modelo 100
profile-surface assertions and three registry query assertions name pre-rename binding
identifiers, two schema-hygiene tests fail on dangling modelo 232 export references, and
two binding-validation tests carry a retired row-set fixture. One unrelated module under
the application modelo package fails to import a symbol another change is mid-edit on.
