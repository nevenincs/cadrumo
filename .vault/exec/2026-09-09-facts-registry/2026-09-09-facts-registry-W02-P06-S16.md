---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:715fbeae88480f1b005c062d02788937555e33a189bc33a0e99272ea44c48890'
step_id: 'S16'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Register statutory category profiles and dated caps

## Scope

- `src/cadrumo/domain/categories/registry.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/categories/registry.py`
- `A` `src/cadrumo/domain/categories/tests/test_fact_provider.py`
- `A` `src/cadrumo/_data/registry/aeat/legal/category-profile-sources.toml`
- `verify:` `uv run pytest -q src/cadrumo/domain/categories/tests/test_fact_provider.py src/cadrumo/domain/categories/tests/test_registry.py src/cadrumo/domain/categories/tests/test_statutory_cap_schedule.py src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/categories/registry.py src/cadrumo/domain/categories/tests/test_fact_provider.py src/cadrumo/domain/calculations/registry/facts/providers.py` -> `pass`
