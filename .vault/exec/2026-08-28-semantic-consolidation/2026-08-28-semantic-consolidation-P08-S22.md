---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-29'
modified: '2026-08-29'
body_schema: 'body-v2'
body_hash: 'sha256:50c1882c096b4129be4aaed810ae2804f4dd0eff9d9869f6351196e46b2d5d6c'
step_id: 'S22'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the zero-to-one-hundred percentage scale once, keeping it distinct from the share alias rather than conflating two scales

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/core/percentage.py`
- `M` `src/cadrumo/domain/bienes_inversion/__init__.py`
- `M` `src/cadrumo/domain/calculations/registry/_m303_orden_raw_models.py`
- `M` `src/cadrumo/domain/calculations/registry/m303_orden_projection_models.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding296_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `M` `src/cadrumo/domain/contribuyente/assets/__init__.py`
- `M` `src/cadrumo/domain/contribuyente/inventory/__init__.py`
- `M` `src/cadrumo/domain/iva/_prorrata.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_prorrata.py src/cadrumo/domain/bienes_inversion` -> `pass`
