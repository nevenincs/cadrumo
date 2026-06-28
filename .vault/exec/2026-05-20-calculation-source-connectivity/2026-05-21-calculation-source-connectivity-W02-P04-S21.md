---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S21'
related:
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# `calculation-source-connectivity` `W02.P04.S21`

Enrolled relation-prefill values in the source mesh and added duplicate relation ownership protection.

- Modified: `src/aeat/application/aggregation/_source_mesh.py`
- Modified: `src/aeat/application/aggregation/test_source_mesh.py`
- Modified: `src/aeat/application/calculations/_relation_prefill.py`
- Modified: `src/aeat/application/calculations/__init__.py`
- Created: `src/aeat/application/calculations/test_relation_prefill_source_mesh.py`

## Description

`CalculationSourceResolution` now has a `relation_values` channel with strict frozen serialization. `merge_source_resolutions` claims relation ownership independently from binding and casilla ownership, raising a duplicate-relation diagnostic when two resolvers try to own the same relation output.

`RelationPrefillSourceResolver` wraps `resolve_relations_from_local_store` and emits relation values plus provenance refs derived from the contributing source filing year and periods.

## Tests

Focused validation passed:

- `uv run pytest src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_source_mesh_profile_live.py src/aeat/application/modelo/test_profile_binding.py src/aeat/application/calculations/test_binding_prefill.py src/aeat/application/calculations/test_relation_prefill_source_mesh.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py`
- `uv run --no-sync ruff check` on the touched source-mesh, profile, relation-prefill, and modelo action files.
