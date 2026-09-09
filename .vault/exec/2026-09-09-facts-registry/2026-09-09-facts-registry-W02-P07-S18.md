---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1c2d7e1ea2e51f0c559a85f90f3dad1be804d9f7444513a4a4823fd9806a9488'
step_id: 'S18'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---


# Register convenio overrides as a typed provider adapter

## Scope

- `src/cadrumo/domain/calculations/registry/convenio.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/convenio.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_convenio_provider.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W02-P07-S18.md`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_convenio_provider.py src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py src/cadrumo/domain/calculations/registry/tests/test_modelo_210_registry.py -q` -> `pass`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_validation.py src/cadrumo/domain/calculations/registry/facts/tests/test_resolution.py -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/convenio.py src/cadrumo/domain/calculations/registry/facts/tests/test_convenio_provider.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/convenio.py src/cadrumo/domain/calculations/registry/facts/schema.py src/cadrumo/domain/calculations/registry/facts/tests/test_convenio_provider.py` -> `pass`
