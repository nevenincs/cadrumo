---
tags:
  - '#audit'
  - '#calculation-source-connectivity'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# `calculation-source-connectivity` Code Review

SRCMESH-001 | HIGH | Clean checkout broke when `_actions.py` referenced an uncommitted borrador resolver
`0fc900b29` routed Modelo 100 calculation through `Modelo100BorradorSourceResolver`, but the defining module changes in `src/aeat/application/modelo/_borrador_binding.py` were not included in that commit. A clean checkout at that commit would fail import/collection for Modelo application tests. Remediated by `1a4b46fdc`, which committed the resolver, its tests, and the S22 execution record.

SRCMESH-002 | LOW | Borrador provenance used a raw snapshot id under a `sha256:` fingerprint prefix
`src/aeat/application/modelo/_borrador_binding.py` emitted `sha256:{snapshot_id}` for borrador provenance, which looked like a digest but was only the raw source id. Remediated by `f019af6eb`, which hashes the snapshot id and adds a focused resolver assertion in `src/aeat/application/modelo/test_borrador_binding.py`.

SRCMESH-003 | INFO | Focused source-connectivity gate passes after remediation
Ran `uv run pytest src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_source_mesh_profile_live.py src/aeat/application/modelo/test_profile_binding.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/calculations/test_binding_prefill.py src/aeat/application/calculations/test_relation_prefill_source_mesh.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py src/aeat/application/calculations/test_observations_repository_roundtrip.py::test_calculation_observation_iter_modelo_enumerates_decrypted_records`: 54 passed. Ran `uv run --no-sync ruff check` across the touched source-connectivity files: all checks passed.

SRCMESH-004 | LOW | Invoice catalogue enrollment is scalar-only until row-value transport lands
`src/aeat/application/invoices/_source_resolver.py` resolves scalar invoice binding values and emits source refs/fingerprints, but `CalculationSourceResolution` does not yet carry row values. This is recorded in the S25 execution note and should be closed by the later invoice/counterpart row-source work before treating Modelo 349 export rows as source-mesh complete. Current focused S25 validation: `uv run pytest src/aeat/application/invoices/test_source_resolver.py` passed; `uv run --no-sync ruff check src/aeat/application/invoices/_source_resolver.py src/aeat/application/invoices/test_source_resolver.py src/aeat/application/invoices/__init__.py` passed.
