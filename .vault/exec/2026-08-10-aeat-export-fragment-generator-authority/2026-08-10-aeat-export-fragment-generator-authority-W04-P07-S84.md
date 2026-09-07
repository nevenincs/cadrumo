---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:84d33ebae980195689cd4b15926159ba43b0348507d68922fa812d22008586cb'
step_id: 'S84'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Introduce the typed M303 fourth-quarter to Modelo 390 annual-summary handoff over the one canonical simplified-regime annual result, carrying strict source and target calculation identity, year, period, revision, evidence and digest checks, and atomically retire the scalar-only box-79 relation when boxes 74-83 arrive through the typed handoff

## Scope

- `src/cadrumo/core/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/domain/modelos/`
- `src/cadrumo/application/calculations/`
- `src/cadrumo/application/modelo/`
- `src/cadrumo/adapters/persistence/profile/`
- `src/cadrumo/_data/registry/aeat/modelos/390/`

## Changes

- `M` `src/cadrumo/core/aggregation.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `src/cadrumo/domain/modelos/calculation_revision.py`
- `M` `src/cadrumo/domain/modelos/calculation_revision_identity.py`
- `A` `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/m303_regimen_simplificado_annual_summary_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_m390_m303_regimen_simplificado_annual_summary_bindings.py`
- `A` `src/cadrumo/application/calculations/m303_regimen_simplificado_annual_summary.py`
- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `src/cadrumo/application/modelo/export.py`
- `M` `src/cadrumo/application/modelo/filing_actions.py`
- `M` `src/cadrumo/application/modelo/revision_persistence.py`
- `M` `src/cadrumo/application/modelo/verification_actions.py`
- `M` `src/cadrumo/application/modelo/tests/test_modelo_390_303_simplificado_fold_in_live.py`
- `A` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/bindings/0009-m303-regimen-simplificado-annual-summary.toml`
- `A` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0009-m303-regimen-simplificado-annual-summary.toml`
- `A` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/bindings/0009-m303-regimen-simplificado-annual-summary.toml`
- `A` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/bindings/0009-m303-regimen-simplificado-annual-summary.toml`
- `verify:` `uv run python -u -m pytest -q src/cadrumo/application/modelo/tests/test_modelo_390_303_simplificado_fold_in_live.py src/cadrumo/domain/calculations/registry/tests/test_m390_m303_regimen_simplificado_annual_summary_bindings.py src/cadrumo/domain/calculations/registry/tests/test_relation_handoff_paths.py::test_bundled_handoff_paths_have_one_owner_and_preserve_provenance src/cadrumo/domain/calculations/registry/tests/test_relation_handoff_inventory.py::test_relation_handoff_inventory_enumerates_every_validated_relation` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/calculations/m303_regimen_simplificado_annual_summary.py src/cadrumo/domain/calculations/registry/m303_regimen_simplificado_annual_summary_bindings.py src/cadrumo/domain/modelos/calculation_revision.py src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py src/cadrumo/core/filing_projection_ref.py` -> `pass`
