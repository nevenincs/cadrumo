---
tags:
  - '#exec'
  - '#period-grammar-standardisation'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S24'
related:
  - "[[2026-06-11-period-grammar-standardisation-plan]]"
---




# Replace the period: str fields in the aggregation service, source mesh and retenciones models with core.Period

## Scope

Cluster C — aggregation service models:

- `src/aeat/application/aggregation/_retenciones.py`
- `src/aeat/application/aggregation/_counterpart.py`
- `src/aeat/application/aggregation/_foreign_assets.py`
- `src/aeat/application/aggregation/_service.py`
- `src/aeat/application/aggregation/_registry_provider.py`
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/application/aggregation/tests/test_retenciones.py`
- `src/aeat/application/aggregation/tests/test_per_modelo_service.py`
- `src/aeat/application/aggregation/tests/test_service.py`
- `src/aeat/application/aggregation/tests/test_per_modelo_registry_provider.py`
- `src/aeat/application/aggregation/tests/test_counterpart.py`

`_source_mesh.py` (CalculationSourceContext.period) and ~26 resolver files were deferred as cluster C2 — too large for one coherent atomic pass.

## Description

- Added `_coerce_period` function and `_PeriodField = Annotated[Period, BeforeValidator(_coerce_period)]` to `_retenciones.py`, `_counterpart.py`, `_foreign_assets.py`, and `_service.py`; coercion accepts inbound combined strings via `parse_canonical_period` at the pydantic boundary so stored values are always a typed `Period`
- Re-typed `RetencionesAggregation.period` from `str = Field(min_length=1)` to `_PeriodField` in `_retenciones.py`
- Changed 7 aggregator function signatures from `period: str` to `period: Period` in `_retenciones.py`: `_aggregate_for_modelo`, `aggregate_retenciones_111/115/123/180/190/193`
- Re-typed `CounterpartAggregation.period` and changed `aggregate_counterpart_347/349` signatures to `period: Period` in `_counterpart.py`; `CounterpartObservation.operation_period` left as `str` (not a filing-period field)
- Re-typed `ForeignAssetsAggregation.period` and changed `aggregate_foreign_assets_720` signature to `period: Period` in `_foreign_assets.py`
- Re-typed `PerModeloAggregationLogFields.period`, `PerModeloAggregationCommand.period`, and `PerModeloAggregationResult.period` to `_PeriodField` in `_service.py`; updated `as_extra()` to emit `self.period.registry_token` (bare token, e.g. "1T")
- Updated `_aggregate_retenciones` and `_aggregate_counterpart` helper signatures to `period: Period` in `_service.py`
- Added `Period` import to `_registry_provider.py`; re-typed `PerModeloRegistryBindingResolution.period` to `Period` (receives typed `Period` from `PerModeloAggregationResult`)
- Updated `_modelo.py` CLI emit: `result.period.registry_token` → `ModeloAggregateResult.period` (str-typed CLI payload); `f"period\t{result.period.registry_token}"` in text lines
- Updated all 5 test files: replaced combined-string fixtures (`"2025-Q1"`, `"2025"`) with module-level `Period.from_year_and_code(year, token)` constants; updated `as_extra()` assertion from `"period": "2025-Q1"` to `"period": "1T"` (registry_token); kept `operation_period="2025"` as str in counterpart-observation fixtures

## Outcome

- Import smoke: clean
- `pytest` on the 5 affected test files: 68 passed, 0 failed
- `ruff check` on all 6 production files: All checks passed
- Commit: `156fa36db` — `refactor(aggregation): typed core.Period on per-modelo aggregation + retenciones (W02.P08 cluster C)`

## Notes

`CalculationSourceContext.period` in `_source_mesh.py` plus the ~26 resolver files that consume it (cluster C2) were judged too large to land coherently in one atomic pass. They are deferred as a follow-up cluster. The `CounterpartObservation.operation_period` field is a calendar-year string for 347/349 grouping, not a filing-period axis, and was intentionally left as `str`.

The `_coerce_period` BeforeValidator pattern allows the CLI and test callsites that still pass combined strings to construct aggregation models without modification; the parse boundary is at the pydantic BeforeValidator, not at the callers.
