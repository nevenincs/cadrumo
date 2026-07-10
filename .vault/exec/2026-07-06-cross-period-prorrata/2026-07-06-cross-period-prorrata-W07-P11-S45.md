---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-08'
step_id: 'S45'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# design and implement the calculation-order seam that exposes current-year prorrata volume, definitive percentage, and deductible-total values to the prorrata_regularizacion resolver without reimplementing formula business logic

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`
- `src/aeat/domain/calculations/registry/_formula_initial_values.py`
- `src/aeat/application/modelo/tests/`

## Description

- Re-ran live plan status and confirmed `W07.P11.S45` was the next open step with no missing exec records.
- Re-grounded the step through semantic search for source-resolution timing, registry initial values, and prorrata regularizacion materialisation before editing.
- Added a public registry helper that identifies casillas seeded before formula evaluation, so staged source resolvers can distinguish declared/bound seed values from values computed by the registry engine.
- Added a no-persist registry-engine materialisation seam in the modelo calculation action layer. The helper accepts already-resolved source channels, delegates input assembly and formula evaluation to `calculate_registry_snapshot`, and returns read-only values plus missing/unresolved casilla ids.
- Added the prorrata-specific selector-order view for current deductible-total, declared annual con-derecho volume, declared annual total volume, and definitive prorrata percentage.
- Added a focused application test against the bundled AEAT Manual IVA prorrata oracle. The test proves the seam exposes manual volume seeds and engine-computed deductible total / definitive percentage without duplicating formula logic in the resolver layer.
- Ran the mandatory code-review pass over the changed implementation and test surface.

## Outcome

- S45 is complete: `prorrata_regularizacion` now has a calculation-order seam it can consume in S46/S47, while the source remains unenrolled and no new source kind, resolver convention, or validator convention was introduced.
- The seam does not persist draft revisions and does not allow computed casillas to be supplied through the input channel. Computed values are read only after the normal registry engine has materialised them.
- The S44 M390 follow-up remains respected: S45 provides current-value materialisation only; automatic resolver binding values and live source enrollment remain owned by `W07.P11.S46` and `W07.P12.S47`.
- Review finding status: no open S45 implementation findings.

## Notes

- Verification passed: `uv run --no-sync ruff check src\aeat\application\modelo\_calculation_actions.py src\aeat\domain\calculations\registry\_formula_initial_values.py src\aeat\domain\calculations\registry\__init__.py src\aeat\application\modelo\tests\test_prorrata_regularizacion_source_timing.py`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_prorrata_regularizacion_source_timing.py src\aeat\application\calculations\tests\test_prorrata_regularizacion_oracle.py src\aeat\application\modelo\tests\test_prorrata_regularizacion_advisory.py -n 0` (8 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_actions.py src\aeat\application\modelo\tests\test_calculate_input.py src\aeat\application\modelo\tests\test_calculate_binding_channel.py -n 0` (44 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_unresolved_binding_diagnostics.py src\aeat\application\modelo\tests\test_source_boundary_and_enrollment.py src\aeat\application\modelo\tests\test_bucket_aggregation_flow.py src\aeat\application\modelo\tests\test_source_mesh_calculation.py -n 0` (31 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\domain\calculations\registry\tests\test_cross_dependency_calculations.py src\aeat\domain\calculations\registry\tests\test_committed_registry.py src\aeat\domain\calculations\registry\tests\test_m303_2024_regimen_general_manual_worked_example.py -n 0` (57 passed).
