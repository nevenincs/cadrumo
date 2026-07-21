---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S20'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# Foreign-assets 720 correctness gate follow-up

## Scope

- `src/aeat/application/aggregation/tests/test_per_modelo_service.py`

## Description

- Add a Modelo 720 per-modelo correctness gate in `src/aeat/application/aggregation/tests/test_per_modelo_service.py`.
- Build a real mixed foreign-asset fixture with two account assets whose class total crosses the 50,000 EUR reporting floor and one sub-floor security control that must be excluded from declarable rows.
- Assert the per-modelo service output equals the prior `aggregate_foreign_assets_720` result.
- Project that prior aggregate through `_registry_observations_from_foreign_assets_aggregation` and the live M720 registry `resolve_foreign_asset_binding_row_values`, asserting the exact row-indexed binding map for the two declarable account rows.
- Call `ForeignAssetsAggregationSourceResolver.resolve(...)` against the live M720 snapshot and assert the resolver selects the same declarable provenance and ledger transaction id while leaving scalar `binding_values` empty.

## Outcome

- The aggregate-to-live-registry row projection is proven exact for the M720 fixture.
- P03.S20 remains unchecked. The current `CalculationSourceResolution` envelope has scalar `binding_values` and typed `detail_rows`, but no row-indexed binding-value channel for `dict[(binding_id, row_index), Decimal | str]`; `ForeignAssetsAggregationSourceResolver` validates the row values and discards them instead of returning them.
- Formal blocker: `DFR-D9-P03-S20-M720-ROW-INDEXED-ENVELOPE`. Completing S20 exactly as written requires a coordinator-approved M720 row carrier strategy before the resolver can expose the prior aggregate output through the live mesh.
- Verification passed:
  - `uv run --no-sync ruff check src/aeat/application/aggregation/tests/test_per_modelo_service.py`
  - `uv run --no-sync python -m py_compile src/aeat/application/aggregation/tests/test_per_modelo_service.py`
  - `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_per_modelo_service.py::test_foreign_assets_m720_registry_rows_match_prior_aggregate_exactly src/aeat/application/aggregation/tests/test_foreign_assets.py::TestForeignAssetSourceResolver::test_resolver_validates_declarable_m720_rows_against_live_registry`
  - `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_per_modelo_service.py src/aeat/application/aggregation/tests/test_foreign_assets.py`

## Notes

- No P03.S20 plan check was run. This record is evidence plus formal deferral inventory, not closure.
- No resolver-envelope, registry, resolver-enrollment, or `_calculation_actions.py` edit was made.

## Retry check (2026-07-04, observed at `f4ed27f35a`)

- Authoritative plan status remains open; P03.S20 is still unchecked behind P03.S21.
- Current focused M720 service run remains red:
  `uv run --no-sync pytest -q -n 0 src/aeat/application/aggregation/tests/test_per_modelo_service.py -k "foreign_asset or foreign_assets or m720 or 720"`
  wrote full output to
  `<operator-home>\AppData\Local\Temp\aeat-d9-retry-foreign-assets-20260704.log`
  and exited `1` (`1 failed`, `1 passed`, `22 deselected`).
- The exact M720 row-projection test now fails before reaching its equality assertions because
  registry authority load still sees the non-authored untracked Modelo 145 scaffold, which lacks
  official workbook parity coverage and any casilla.
- No P03.S20 plan check was run.
