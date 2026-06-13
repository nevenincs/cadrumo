---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S20'
related:
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# `calculation-source-connectivity` `W02.P04.S20`

Enrolled previous-filing binding prefill behind a source mesh resolver wrapper.

- Modified: `src/aeat/application/calculations/_multi_year.py`
- Modified: `src/aeat/application/calculations/__init__.py`
- Modified: `src/aeat/application/calculations/test_binding_prefill.py`

## Description

`PreviousFilingSourceResolver` resolves `source = "previous_filing"` binding values through the existing local-store prefill path, then exposes those values as a `CalculationSourceResolution` with previous-filing provenance. The test asserts parity with `resolve_bindings_from_local_store` using the real Modelo 390 annual-total prefill path.

## Tests

Focused validation passed:

- `uv run pytest src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_source_mesh_profile_live.py src/aeat/application/modelo/test_profile_binding.py src/aeat/application/calculations/test_binding_prefill.py src/aeat/application/calculations/test_relation_prefill_source_mesh.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py`
- `uv run --no-sync ruff check` on the touched source-mesh, profile, relation-prefill, and modelo action files.
