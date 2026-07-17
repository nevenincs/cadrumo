---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Orchestrate per-(ejercicio,sector) register entries and per-sector routing in the regime-aware aggregation

## Scope

- `src/aeat/domain/prorrata_register/__init__.py`
- `src/aeat/application/aggregation/_iva_ledger.py`

## Description

- Carry the operator-declared sector onto the transient IVA observation: add `prorrata_sector_id: str | None` to `IvaLedgerObservation` in `src/aeat/domain/calculations/registry/_ledger_bindings.py`, and populate it from the source transaction in `_iva_observation` (settlement and both cash-accounting paths) in `src/aeat/application/aggregation/_iva_ledger.py`.
- Add the `IvaLedgerSectorApportionment` carrier and a `sector_apportionments` tuple on `IvaLedgerProrrataApportionment`: an empty tuple is the whole-entity register (byte-identical), a non-empty tuple carries each declared sector's percentage + regime while the top-level percentage/regime describe the art. 104.Dos common-use apportionment.
- Make `_active_prorrata_apportionment` sector-aware over the existing `(ejercicio, sector_id)`-keyed register: resolve the common `sector_id = None` entry as the base, and when `register.is_sectorized` attach one `IvaLedgerSectorApportionment` per declared sector (each resolved through the shared `resolve_provisional`); factor the per-key resolution into `_sector_scoped_apportionment`.
- Branch `resolve_iva_ledger_binding_values` on `sector_apportionments`: route to a new `_apply_sector_apportionment` that partitions observations by `prorrata_sector_id` (unknown / untagged inputs fall to the art. 104.Dos common apportionment) and sums each sector's `_apportioned_deducible_cuota` contribution. The whole-entity general and especial branches are UNCHANGED, so the non-sectorized path is byte-identical.
- Extract `_apportioned_deducible_cuota` as the per-partition primitive (general flat multiply / especial per-classification routing), consumed by the sector path; both branches resolve through the SAME canonical registry resolver.

## Outcome

Sector-aware routing now applies each differentiated sector's provisional percentage to its own deducible cuota (LIVA arts. 9.1.c / 101), with common-use inputs apportioned at the art. 104.Dos common percentage. The whole-entity path is proven byte-identical two ways: the five landed S12 general/especial regressions still pass unchanged, and a new S18 regression proves a one-sector register (all inputs in the sector) is byte-for-byte equal to the whole-entity general result. A second S18 wiring test proves two sectors with a >50-point spread (90% / 20%) plus a common-use input each apply their own percentage independently, never a single whole-entity percentage. Gates green on the owner slice: ruff, ruff format, ty clean; registry collect-only clean (2948 collected); 463 aggregation-suite tests plus 7 apportionment regressions pass under `-n0`.

## Notes

- A sectorized register requires its `sector_id = None` common entry to apportion common-use inputs; absent it, no apportionment applies (exactly as for any register with no whole-entity entry today) — this is consistent with existing behaviour, not a new silent path, and is documented in `_active_prorrata_apportionment`.
- The full AEAT-oracle-or-honest-hand-constructed verification with anti-tautology assertions is the S20 deliverable; the S18 two-sector test is a structural wiring proof (it asserts the three percentages are applied independently), and its docstring says so.
- Pre-existing owner-distinct failure (NOT this step): `test_ledger_iva_aggregation_binding_annual.py::test_modelo_390_annual_iva_pipeline_...` raises `missing binding fact for casilla 'iva.anual.regularizacion-bienes-inversion' (modelo-390-bienes-inversion-regularizacion-casilla-63)`. This is the bienes-inversión campaign's active M390 production work (source `bienes_inversion_regularizacion`, commit `1c582e17b8`), not ledger IVA; my sector routing touches no bienes-inversion surface. Recorded as peer-owned per prior audit tasks, not a sector-routing regression.
