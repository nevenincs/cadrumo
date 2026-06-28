---
tags:
  - "#exec"
  - "#calculation-source-connectivity"
date: 2026-05-21
modified: '2026-05-21'
plan: 2026-05-20-calculation-source-connectivity-plan
wave: W01
phase: W01.P02
steps:
  - W01.P02.S07
  - W01.P02.S08
  - W01.P02.S09
  - W01.P02.S10
  - W01.P02.S11
  - W01.P02.S12
status: complete
---
# W01.P02 Existing Ledger Path Wrapper

Implemented source mesh wrappers for the existing ledger-backed calculation paths without enrolling them into the default modelo calculation orchestrator yet.

## Code Changes

- Added `LedgerIvaAggregationSourceResolver` in `src/aeat/application/aggregation/_modelo_bindings.py`.
- Added `LedgerRentaExpenseAggregationSourceResolver` in `src/aeat/application/aggregation/_modelo_bindings.py`.
- Added `OssIossLedgerSourceResolver` in `src/aeat/application/aggregation/_oss_ioss.py`.
- Extended source diagnostics with `source_issue` so existing IVA and Renta aggregation issues can be carried through resolver output.
- Exported the resolver classes through `src/aeat/application/aggregation/__init__.py`.
- Added parity coverage in `src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py`.

## Grounding

- IVA resolver delegates to the existing repository-backed IVA aggregation and registry binding resolver.
- Renta resolver delegates to the existing repository-backed Renta expense aggregation and registry binding resolver.
- OSS / IOSS resolver delegates to the existing candidate validation and registry binding resolver.
- Tests compare resolver output to current bridge functions rather than recomputing expected tax results in the test.

## Verification

- `uv run ruff check src/aeat/application/aggregation/_source_mesh.py src/aeat/application/aggregation/_modelo_bindings.py src/aeat/application/aggregation/_oss_ioss.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py`
- `uv run pytest src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py -q --tb=short`

Both checks passed on 2026-05-21.

## Residual Work

- W01.P03 remains open: route the default bucket calculation and CLI calculation path through source mesh resolution.
- Source mesh wrappers are currently available as application-layer adapters; production orchestration still uses the legacy bridge until W01.P03 is completed.
