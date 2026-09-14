---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:c6d543154c67cec019f72d8214bb788364817160c122d914baa8a494ae8c43db'
step_id: 'S06'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# Relocate registry authoring tests and compiler-only modules

## Scope

- `src/cadrumo/domain/calculations/registry/`

## Changes

- `M` `dev/packaging/tests/test_authority_runtime_boundary.py`
- `M` `src/cadrumo/application/aggregation/tests/test_ledger_income_chain_aeat_exempt_worked_example.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/_registry_scenarios_support.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/scenarios.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_deduccion_madrid_nacimiento_adopcion.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_m100_2024_final_settlement_chain_wiring.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_reduccion_art_84_conjunta.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_registry_scenarios.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_renta_chain_behaviour.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_schema.py`
- `M` `dev/registry/tests/test_m100_2020_estimacion_directa_manual_worked_example.py`
- `M` `dev/registry/tests/test_m100_2020_rendimientos_trabajo_despido_manual_worked_example.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_continuidad_completeness_ratchet.py` -> `dev/registry/tests/test_continuidad_completeness_ratchet.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_bracket_accumulated_cuota_continuity.py` -> `dev/registry/tests/test_bracket_accumulated_cuota_continuity.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_export_header_key_naming.py` -> `dev/registry/tests/test_export_header_key_naming.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_modelo_123_registry.py` -> `dev/registry/tests/test_modelo_123_registry.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_modelo_130_registry.py` -> `dev/registry/tests/test_modelo_130_runtime_and_source_grounding.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_modelo_180_registry.py` -> `dev/registry/tests/test_modelo_180_registry.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_modelo_190_registry.py` -> `dev/registry/tests/test_modelo_190_registry.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_modelo_193_registry.py` -> `dev/registry/tests/test_modelo_193_registry.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py` -> `dev/registry/tests/test_modelo_200_registry.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_modelo_216_registry.py` -> `dev/registry/tests/test_modelo_216_registry.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_rate_box_export_offsets.py` -> `dev/registry/tests/test_modelo_390_rate_box_export_offsets.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_unmodelled_regimen_rate_box_preconditions.py` -> `dev/registry/tests/test_modelo_390_unmodelled_regimen_rate_box_preconditions.py`
- `R` `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_volumen_operaciones.py` -> `dev/registry/tests/test_modelo_390_volumen_operaciones.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/record_design_xsd_support.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_legal_anchor_verification_ratchet.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_modelo_131_regulatory_floor_predicate.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_record_design_xsd_repair.py`
- `A` `dev/registry/tests/test_modelo_200_revision_source_tiering.py`
- `A` `dev/registry/tests/test_verification_rounding_registry_vocabulary.py`
- `R` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas/c00394__c00400.toml` -> `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas/c00394__cDP200010+00399.toml`
- `R` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas/c00548__c00554.toml` -> `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas/c00548__cDP200010+00552.toml`
- `R` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas/c00604__c00610.toml` -> `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas/c00604__cDP200010+00605.toml`
- `R` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas/c00618__c00624.toml` -> `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/casillas/c00618__cDP200010+00619.toml`
- `R` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/casillas/civa.anual.repercutido.general__civa.anual.resultado-regimen-general.toml` -> `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/casillas/civa.anual.regularizacion-prorrata-definitiva.toml`
- `verify:` `uv run pytest -n 0 --confcutdir=dev/packaging/tests dev/packaging/tests/test_authority_runtime_boundary.py -q` -> `pass`
- `verify:` `uv run pytest -n 0 --noconftest -q dev/registry/tests/test_verification_rounding_registry_vocabulary.py dev/registry/tests/test_record_design_xsd_repair.py dev/registry/tests/test_modelo_200_revision_source_tiering.py` -> `pass`
- `verify:` `uv run ruff format --check dev/packaging/tests/test_authority_runtime_boundary.py dev/registry/tests/test_export_header_key_naming.py` -> `pass`
- `verify:` `uv run ruff check dev/packaging/tests/test_authority_runtime_boundary.py dev/registry/tests/test_export_header_key_naming.py` -> `pass`
- `verify:` `uv run python -m py_compile dev/registry/tests/test_modelo_130_runtime_and_source_grounding.py dev/registry/tests/test_modelo_390_rate_box_export_offsets.py` -> `pass`
- `verify:` `git diff --check -- dev/packaging/tests/test_authority_runtime_boundary.py dev/registry/tests src/cadrumo/domain/calculations/registry/tests` -> `pass`

## Notes

Broad scenario collection currently reaches the migrated callers but fails in unrelated in-progress W04 code: the tracked authority artifact does not yet contain the new IVA catalogue entries required by typed reconstruction, and `IvaRate` does not yet provide Pydantic schema support. The S06 static migration, isolated authored-source tests, and packaging boundary are independently green.
