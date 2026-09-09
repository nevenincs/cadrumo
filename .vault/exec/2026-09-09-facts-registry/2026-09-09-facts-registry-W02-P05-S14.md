---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d03e7a4e408f539b55ab5b7bc8ae021da7b574d8152820941937f1b8019b5866'
step_id: 'S14'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Register recargo by applied rate and operation date

## Scope

- `src/cadrumo/domain/iva/recargo_equivalencia.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py`
- `M` `src/cadrumo/domain/iva/recargo_equivalencia.py`
- `verify:` `uv run python -m pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py src/cadrumo/domain/iva/tests/test_recargo_rate_applied_rate_lookup.py src/cadrumo/domain/iva/tests/test_recargo_equivalencia.py -q` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/iva/recargo_equivalencia.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/iva/recargo_equivalencia.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py` -> `pass`
