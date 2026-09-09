---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:19a1120820a3e8908b10a0919c965ed2491f364b6d2e5700b5592d56153d55d9'
step_id: 'S17'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Register classified legal calendar and deadline facts

## Scope

- `src/cadrumo/domain/deadlines`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/deadlines/festivos.py`
- `A` `src/cadrumo/domain/deadlines/tests/test_fact_provider.py`
- `verify:` `uv run pytest -q src/cadrumo/domain/deadlines/tests/test_fact_provider.py src/cadrumo/domain/deadlines/tests/test_festivos.py src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/deadlines/festivos.py src/cadrumo/domain/deadlines/tests/test_fact_provider.py src/cadrumo/domain/calculations/registry/facts/providers.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/deadlines/festivos.py src/cadrumo/domain/deadlines/tests/test_fact_provider.py` -> `pass`
