---
step_id: S66
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-P17-S67]]"
---

# cross-domain-continuity P17.S66 — CLI-level cross-modelo calculation tests

## Outcome

New file `src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py`
with 5 tests covering Modelo 200, 202, 130, 303, and 100 through the real
`aeat` CLI against an `isolated_runtime_profile` backend (real KEK/DEK,
real SQLite). No mocks. No unsecured-monkeypatch backend.

## Tests delivered

- `test_modelo_200_micro_empresa_pyme_cuota_2024` — oracle numeric assertion
- `test_modelo_202_art_40_2_cuota_incn_below_threshold` — oracle numeric assertion
- `test_modelo_130_resultado_apartado_i_direct_estimation` — oracle numeric assertion
- `test_modelo_303_calculate_surface_is_reachable` — structural surface test
- `test_modelo_100_calculate_surface_is_reachable` — structural surface test

## Key implementation decisions

- M303 and M100 are surface tests (no numeric oracle) because their cuota
  depends on ledger-sourced bindings requiring a full transaction ingestion
  pipeline outside this fixture's scope. Oracle assertions for those modelos
  live in the source-mesh and registry-level test suites.
- Profile seeded via `UserProfileLifecycleRepository.save()` directly, bypassing
  `config profile create` which would conflict with the already-provisioned
  bucket manifest.
- Natural-person profile requires minimum required facts:
  `irpf_income_categories="actividad_economica"`, `irpf.estimation_regime`,
  `iva.regime`, `provenance.source`.
- M200 work create period token: `0A` (not `A`).
- M202 work create period token: `1P` (not `2026-1P`).
- M202 calculate requires `--binding modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores=0`
  for the `previous_filing` bound casilla 30.
- M200 calculate requires `--relation modelo-200-2024-rel-202-pagos-fraccionados=0`.
- M200 base imponible input casilla: `DP200014:00552` (manual); `DP200014:01330`
  is computed (post-nivelación base); also supply `DP200014:01033=0` and
  `DP200014:01034=0` (reserva de nivelación adjustments).

## Gate status

All 5 tests pass. pyright: 0 errors. ruff: clean.
