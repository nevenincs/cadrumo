---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:5284fd5e867455d660c83cd9f76c1c2aef07a6b39ac7e36237b2380eed0f08da'
step_id: 'S13'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Register IVA rate schedules as typed dated provider adapters

## Scope

- `src/cadrumo/domain/iva/rates.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/resolution.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/schema.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_iva_rate_provider.py`
- `M` `src/cadrumo/domain/iva/rates.py`
- `verify:` `uv run python -m pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_iva_rate_provider.py src/cadrumo/domain/iva/tests/test_rates.py -q` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/iva/rates.py src/cadrumo/domain/calculations/registry/facts/schema.py src/cadrumo/domain/calculations/registry/facts/resolution.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_iva_rate_provider.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/iva/rates.py src/cadrumo/domain/calculations/registry/facts/schema.py src/cadrumo/domain/calculations/registry/facts/resolution.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_iva_rate_provider.py` -> `pass`
