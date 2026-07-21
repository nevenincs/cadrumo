---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# Author a counterpart 347/349 ModeloSourceResolver returning CalculationSourceResolution that delegates to aggregate_counterpart_347/349, behaviour-preserving against the existing counterpart suites

## Scope

- `src/aeat/application/aggregation/_counterpart.py`

## Description

- Add `CounterpartAggregationSourceResolver` as the counterpart source-mesh adapter for Modelo 347/349.
- Delegate source rollup to the existing `aggregate_counterpart_347` / `aggregate_counterpart_349` functions before resolving registry binding values.
- Adapt counterpart rollups into the registry `CounterpartAggregationObservation` contract and preserve the existing M349 payable-summary mirror fold.
- Add real-registry tests proving M349 scalar values materialise from supplied counterpart observations and non-counterpart revisions resolve empty.

## Outcome

- Resolver returns `CalculationSourceResolution` with owned counterpart sources, scalar binding values, source transaction ids for selected ledger observations, and provenance only for observations selected by the modelo operation-kind catalogue.
- Existing counterpart/per-modelo aggregation behavior was preserved:
  - `uv run --no-sync ruff check src/aeat/application/aggregation/_counterpart.py src/aeat/application/aggregation/tests/test_counterpart.py`
  - `uv run --no-sync python -m py_compile src/aeat/application/aggregation/_counterpart.py src/aeat/application/aggregation/tests/test_counterpart.py`
  - `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_counterpart.py src/aeat/application/aggregation/tests/test_counterpart_347_cross_cohort_merge.py src/aeat/application/aggregation/tests/test_per_modelo_service.py` (`31 passed`)
  - `uv run --no-sync pytest --collect-only -q src/aeat/application/aggregation/tests/test_counterpart.py src/aeat/application/aggregation/tests/test_counterpart_347_cross_cohort_merge.py src/aeat/application/aggregation/tests/test_per_modelo_service.py` (`31 tests collected`)

## Notes

- No resolver enrollment was performed; `P03.S12` owns `merge_source_resolutions` enrollment and hub-file changes.
- No new binding source kind, resolver convention, or validator convention was introduced.
