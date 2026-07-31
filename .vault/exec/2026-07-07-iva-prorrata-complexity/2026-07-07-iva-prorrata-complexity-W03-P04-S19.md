---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:c2ff37bab783357625fcbbd3613557c69b163d93571fd865537763c370f81a16'
step_id: 'S19'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Run the per-sector provisional/definitive lifecycle (seed and settlement per sector)

## Scope

- `src/aeat/application/prorrata_register/`
- `src/aeat/application/calculations/_prorrata_regularizacion.py`

## Description

- Add the per-sector lifecycle module `src/aeat/application/prorrata_register/_sector_lifecycle.py` and export both functions through the package facade.
- `seed_sector_carried_definitive_from_register` seeds a sector's current-year provisional from the register's own `(ejercicio-1, sector_id)` DEFINITIVE (LIVA art. 105.Uno per sector), returning `None` when the prior year holds no settled sector definitive so the caller surfaces the missing-provisional advisory rather than assuming a percentage. The whole-entity Modelo 303 observation is deliberately NOT consulted — it carries a single filing percentage and cannot supply a per-sector definitive.
- `settle_sector_definitive` computes a sector's year-end definitive from ITS OWN annual con/sin-derecho volumes via `compute_prorrata_definitiva_anual(sector_id=...)` (LIVA art. 105.Cuatro per sector) and writes it back onto the sector's register entry, preserving the provisional fields for the annual regularización compare.

## Outcome

The differentiated-sector lifecycle now runs the landed cross-period mechanism per sector end-to-end: seed the year's provisional from the sector's prior definitive, apportion in-year (the S18 sector-aware aggregation), and settle the sector's definitive from its own volumes. Five real-behaviour tests pass under `-n0`: a settlement derives the sector's definitive from its own volumes; a next-year provisional carries the sector's prior definitive; two sectors with different volumes carry distinct provisionals with a >50-point spread (structural anti-tautology against a cross-sector leak); a sector with no prior definitive seeds `None` (no silent default); and a whole-entity definitive does not leak into a sector's carried provisional. Broader regression green: 33 prorrata_register + regularizacion tests pass. ruff, ruff format, and ty clean; the module imports only through the `domain.iva` and `domain.prorrata_register` package facades.

## Notes

- The pre-existing sector-parameterised primitives were consumed, not rebuilt: the application `ProrrataRegisterService` (declare / record_aeat_autorizada / record_inicio_actividad / get / resolve_provisional), `seed_carried_prior_definitiva_entry` / `evaluate_carried_prior_definitiva_seed`, and `build_interrumpida_tres_ultimos_seed` already thread `sector_id` (the register was sector-keyed from birth), and `compute_prorrata_definitiva_anual` already takes `sector_id`. The only genuine gap this step closes is the register-sourced per-sector carried seed (the whole-entity carried seed reads the Modelo 303 observation, which cannot be per-sector) and the explicit per-sector settlement write-back.
- `_prorrata_regularizacion.py` was in the declared scope but needed no change: its regularización primitives (`derive_prorrata_applicability`, `project_prorrata_regularizacion_feed`) are value-driven and compose per sector, and `build_interrumpida_tres_ultimos_seed` already carries `sector_id`.
- The full AEAT-oracle-or-honest-hand-constructed >50pp two-sector verification with anti-tautology assertions is the S20 deliverable; the S19 tests prove the lifecycle wiring (each sector uses its own prior definitive and its own volumes).
