---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:42ce3336bbd5fcb6baf4ee993b11eb63b5e5654c805367d2c086a94f56d3089d'
step_id: 'S25'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Map summarized aggregation outcomes into one source diagnostic per resolver

## Scope

- `src/aeat/application/aggregation/_modelo_bindings.py`

## Description

- Attempt semantic grounding for source-mesh summary mapping; record the unavailable service and timed-out fallback.
- Import the typed out-of-window summary and source-mesh summary diagnostic builder into `src/aeat/application/aggregation/_modelo_bindings.py`.
- Add `_out_of_window_summary_diagnostics` to translate one aggregation summary into one `CalculationSourceDiagnostic`.
- Prepend summary diagnostics to IVA, Renta income, impatriado income, and Renta gasto source resolver diagnostics.
- Leave binding values, provenance, source transaction ids, and row-level non-summary issue mappings unchanged.

## Outcome
- Converted repository-backed aggregation summaries now surface as one structured source diagnostic per resolver.
- `uv run ruff check src/aeat/application/aggregation/_modelo_bindings.py` passed.
- The direct `_out_of_window_summary_diagnostics` probe passed with count and date-span fields intact.
- `uv run pytest -q -n 0 src/aeat/application/aggregation/tests/test_modelo_source_mesh_ledger.py::test_iva_source_mesh_resolver_resolves_general_sale_and_purchase` passed.

## Notes

- `uv run vaultspec-rag search "modelo bindings source mesh map out_of_window_summary source diagnostic resolver aggregation issues" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for `_modelo_bindings.py`, `_source_mesh.py`, and the converted aggregation result models.
- Dedicated source-mesh summary regression assertions are deferred to S30.
