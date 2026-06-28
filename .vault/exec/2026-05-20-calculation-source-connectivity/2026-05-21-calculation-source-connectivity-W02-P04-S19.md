---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S19'
related:
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# `calculation-source-connectivity` `W02.P04.S19`

Enrolled profile-backed registry bindings in the source mesh while preserving the existing profile binding resolver behavior.

- Created: `src/aeat/application/aggregation/_source_profile.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `src/aeat/application/modelo/_actions.py`
- Created: `src/aeat/application/aggregation/test_source_mesh_profile_live.py`

## Description

`ProfileSourceResolver` wraps the existing profile binding resolver and emits source-mesh binding values, enum binding values, and profile provenance records. The modelo calculation path now invokes that resolver instead of calling profile binding resolution directly, while retaining caller-owned binding precedence.

## Tests

Focused validation passed:

- `uv run pytest src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_source_mesh_profile_live.py src/aeat/application/modelo/test_profile_binding.py src/aeat/application/calculations/test_binding_prefill.py src/aeat/application/calculations/test_relation_prefill_source_mesh.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py`
- `uv run --no-sync ruff check` on the touched source-mesh, profile, relation-prefill, and modelo action files.
