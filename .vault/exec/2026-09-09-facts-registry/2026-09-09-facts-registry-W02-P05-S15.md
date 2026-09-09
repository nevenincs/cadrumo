---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:896700b8f3ac87d661a1220676c19ac7102dc283f744ca937dd3d3a277c13aac'
step_id: 'S15'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Move IVA evidence enforcement into provider validation

## Scope

- `src/cadrumo/domain/iva/_grounding.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_validate.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/validation.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_iva_provider_grounding.py`
- `M` `src/cadrumo/domain/iva/_grounding.py`
- `verify:` `uv run python -m pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_iva_provider_grounding.py src/cadrumo/domain/calculations/registry/facts/tests/test_validation.py src/cadrumo/domain/iva/tests/test_iva_registry_grounding.py -q` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/calculations/registry/_validate.py src/cadrumo/domain/calculations/registry/facts/validation.py src/cadrumo/domain/calculations/registry/facts/tests/test_iva_provider_grounding.py src/cadrumo/domain/iva/_grounding.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/_validate.py src/cadrumo/domain/calculations/registry/facts/validation.py src/cadrumo/domain/calculations/registry/facts/tests/test_iva_provider_grounding.py src/cadrumo/domain/iva/_grounding.py` -> `pass`
