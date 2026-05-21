---
tags:
  - '#audit'
  - '#calculation-source-connectivity'
date: '2026-05-21'
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
