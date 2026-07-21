---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# Author a foreign-assets 720 ModeloSourceResolver returning CalculationSourceResolution that delegates to aggregate_foreign_assets_720, behaviour-preserving against the existing 720 suites

## Scope

- `src/aeat/application/aggregation/_foreign_assets.py`

## Description

- Add `ForeignAssetsAggregationSourceResolver` as the repository-free Modelo 720 source-mesh adapter.
- Delegate threshold semantics to `aggregate_foreign_assets_720` before adapting declarable classes into `Modelo720RowObservation`.
- Validate the adapted rows with `resolve_foreign_asset_binding_row_values` against the live Modelo 720 registry bindings.
- Add real-registry tests proving declarable account rows materialise through the existing row binding resolver and non-720 revisions resolve empty.

## Outcome

- Resolver returns `CalculationSourceResolution` with owned `foreign_asset`, ledger source transaction ids, and provenance for declarable observations.
- Existing scalar `binding_values` stay empty for Modelo 720 because the current envelope has no row-indexed string/decimal channel; no new resolver convention was introduced in this authoring step.
- No resolver enrollment was performed; `P03.S12` owns `merge_source_resolutions` enrollment and deferred-source removal.
- Existing foreign-assets/per-modelo behavior was preserved:
  - `uv run --no-sync ruff check src/aeat/application/aggregation/_foreign_assets.py src/aeat/application/aggregation/tests/test_foreign_assets.py`
  - `uv run --no-sync python -m py_compile src/aeat/application/aggregation/_foreign_assets.py src/aeat/application/aggregation/tests/test_foreign_assets.py`
  - `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_foreign_assets.py src/aeat/application/aggregation/tests/test_per_modelo_service.py` (`34 passed`)
  - `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py` (`4 passed`)

## Notes

- No new binding source kind, resolver convention, or validator convention was introduced.
