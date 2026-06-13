---
tags:
  - "#exec"
  - "#calculation-source-connectivity"
date: 2026-05-21
modified: '2026-05-21'
plan: 2026-05-20-calculation-source-connectivity-plan
wave: W01
phase: W01.P03
steps:
  - W01.P03.S13
  - W01.P03.S14
  - W01.P03.S15
  - W01.P03.S16
  - W01.P03.S17
  - W01.P03.S18
status: complete
---
# W01.P03 Default Calculation Enrollment

Enrolled the default bucket-backed modelo calculation path into source mesh resolution and routed the CLI calculate verb to that same bucket-backed boundary.

## Code Changes

- Replaced the legacy `resolve_modelo_ledger_binding_values_from_repositories` call in `calculate_modelo_revision_from_bucket_aggregation` with source mesh resolver execution and `merge_source_resolutions`.
- Replaced hardcoded ledger binding override checks with source-owned binding and bound-casilla checks derived from resolver-owned source kinds.
- Routed `aeat app modelo work calculate` through `calculate_modelo_revision_from_bucket_aggregation`.
- Added source-owned override rejection coverage for Modelo 303 IVA and Modelo 100 Renta source bindings.
- Added a CLI boundary test ensuring the calculate verb enters the bucket-backed calculation path.
- Added a real CLI persistence roundtrip proving ledger-derived source transaction ids, binding overrides, and typed observation source refs survive `aeat app modelo work calculate`.

## Verification

- `uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_source_mesh_calculation.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py`
- `uv run pytest src/aeat/application/modelo/test_source_mesh_calculation.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/entrypoints/cli/test_modelo.py::test_work_calculate_enters_bucket_source_mesh_calculation_boundary -q --tb=short`
- `uv run ruff check src/aeat/application/aggregation/_source_mesh.py src/aeat/application/aggregation/_modelo_bindings.py src/aeat/application/aggregation/_oss_ioss.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_source_mesh_calculation.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py`
- `uv run pytest src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py src/aeat/application/modelo/test_source_mesh_calculation.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/entrypoints/cli/test_modelo.py::test_work_calculate_enters_bucket_source_mesh_calculation_boundary src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py -q --tb=short`

Both checks passed on 2026-05-21.

## Residual Work

- W02.P04 is next: enroll profile, previous filing, relation prefill, borrador, and IVA wallet decision source families.
