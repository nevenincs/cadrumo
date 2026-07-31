---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:2ca7360c719b3d114a69dc4294d6f8069ace0bae17c3643c9ac3dae2846e21a1'
step_id: 'S30'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Update source-mesh ledger tests for summarized diagnostics

## Scope

- `src/aeat/application/aggregation/tests/test_modelo_source_mesh_ledger.py`

## Description

- Attempt semantic grounding for source-mesh summary diagnostic tests; record the unavailable service and timed-out fallback.
- Rename the IVA source-mesh out-of-period test from suppression to summary behavior.
- Assert the resolver emits one structured source diagnostic with count and filing-date span.
- Preserve the raw full-catalogue aggregation assertion for row-level `OUTSIDE_PERIOD`.

## Outcome
- `src/aeat/application/aggregation/tests/test_modelo_source_mesh_ledger.py` now verifies the source-mesh resolver summary diagnostic path.
- `uv run ruff check src/aeat/application/aggregation/tests/test_modelo_source_mesh_ledger.py` passed.
- `uv run pytest -q -n 0 src/aeat/application/aggregation/tests/test_modelo_source_mesh_ledger.py::test_iva_source_mesh_resolver_summarizes_out_of_period_personal_source_diagnostic` passed.

## Notes

- `uv run vaultspec-rag search "source mesh ledger tests summarized out-of-window diagnostics model bindings" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for the source-mesh test file and resolver mappings.
- Existing resolver coverage in this file exercises the shared mapping through IVA; the source-mesh diagnostic builder itself is covered in `test_source_mesh.py`.
