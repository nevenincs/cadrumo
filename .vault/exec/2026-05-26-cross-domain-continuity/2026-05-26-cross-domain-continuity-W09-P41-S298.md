---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-07'
modified: '2026-07-07'
step_id: 'S298'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R8-ROSA-CRITICAL M100 missing binding for estimacion objetiva regimen

## Scope

- `only renta-2024-modelo-100-estimacion-directa-es-normal binding visible when profile has irpf.estimation_regime=objetiva`
- `need a rendimiento-neto-modulos binding derived from annual M131 sum for IRPF anual under modulos`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/`

## Description

- Ground S298 with RAG searches for `M100 2024 estimacion objetiva modulos binding annual M131 sum rendimiento neto` and `S298`, plus the governing M100/M131 continuity ADR search.
- Add the M100/2024 relation-backed binding `renta-2024-modelo-131-rendimiento-neto-modulos` over Modelo 131 casilla `01`.
- Add the relation `renta-2024-rel-131-rendimiento-neto-modulos` so the live relation-prefill resolver folds M131 1T-4T source observations into the annual M100 binding slot.
- Bind M100 casilla `1481` to the new relation-backed slot, letting the existing `1481 -> 1482 -> 1484` objective-estimation formula chain consume it.
- Update the M100 dependent-model construct and M131 dependency classification so registry provenance and relation membership remain explicit.
- Add live application tests proving an objective-estimation profile folds stored M131 annual source data into M100 objective-estimation net income, while a direct-estimation profile keeps the M131 módulos binding at the not-applicable zero.

## Outcome

- Closed the S298 gap for non-agrarian M100/2024 estimación objetiva módulos: stored quarterly M131 casilla `01` observations now sum into M100 casilla `1481` through the canonical relation-prefill mechanism.
- The existing M100 objective-estimation formulas then carry the value through casillas `1482` and `1484` without duplicating M131 coefficient tables or adding a parallel módulos engine.
- M131 pagos fraccionados remain on the existing casilla `15` relation; S298 adds only the missing net-income relation.
- Direct-estimation behavior remains intact: when the profile marks M131 as not applicable, the new relation-backed binding resolves to explicit zero rather than requiring synthetic M131 filings.
- Validation passed:
  - `uv run --no-sync ruff check src/aeat/application/modelo/tests/test_modelo_100_m131_modulos_fold_in_live.py`
  - `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_modelo_100_m131_modulos_fold_in_live.py`
  - `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_modelo_100_pagos_fraccionados_fold_in_live.py src/aeat/application/modelo/tests/test_modelo_100_m131_modulos_fold_in_live.py`
  - `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_relation_consistency.py src/aeat/domain/calculations/registry/tests/test_relation_closure.py`

## Notes

- The first registry test invocation for relation consistency timed out at the 120 second tool cap; the same command was rerun with a 240 second cap and passed.
- No raw M131 módulo-unit coefficient computation was added. The annual M100 value is derived from already stored M131 casilla `01` source data, matching the existing relation-prefill architecture and the S297 boundary note.
