---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S22'
related:
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# `calculation-source-connectivity` `W02.P04.S22`

Enrolled Modelo 100 borrador binding values behind a source mesh resolver.

- Modified: `src/aeat/application/modelo/_borrador_binding.py`
- Modified: `src/aeat/application/modelo/test_borrador_binding.py`

## Description

`Modelo100BorradorSourceResolver` wraps the existing explicit borrador snapshot binding path and emits source-mesh binding values, enum binding values, and `borrador` provenance records. This closes the clean-checkout gap exposed by the source-connectivity review: the calculation action route already consumed the resolver, so the resolver definition and parity test now land with the plan row.

## Tests

Focused validation passed:

- `uv run pytest src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_profile_binding.py`
- `uv run --no-sync ruff check src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_profile_binding.py src/aeat/application/aggregation/_source_mesh.py`
