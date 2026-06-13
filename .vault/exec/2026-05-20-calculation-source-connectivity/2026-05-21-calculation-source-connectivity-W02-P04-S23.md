---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S23'
related:
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# `calculation-source-connectivity` `W02.P04.S23`

Enrolled Modelo 303 IVA wallet reconciliation decisions as source mesh binding values.

- Modified: `src/aeat/application/calculations/_iva_wallet_reconciliation.py`
- Modified: `src/aeat/application/calculations/__init__.py`
- Modified: `src/aeat/application/calculations/test_iva_wallet_reconciliation.py`

## Description

`IvaWalletDecisionSourceResolver` emits the Modelo 303 prior-compensation binding from a validated wallet reconciliation decision. It rejects target-axis mismatches, blocked decisions, and decisions without a selected amount, and emits provenance for authority sources with a stable decision fingerprint.

## Tests

Focused validation passed:

- `uv run pytest src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_source_mesh_profile_live.py src/aeat/application/modelo/test_profile_binding.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/calculations/test_binding_prefill.py src/aeat/application/calculations/test_relation_prefill_source_mesh.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py src/aeat/application/calculations/test_observations_repository_roundtrip.py::test_calculation_observation_iter_modelo_enumerates_decrypted_records`
- `uv run --no-sync ruff check` on the touched source-connectivity files.
