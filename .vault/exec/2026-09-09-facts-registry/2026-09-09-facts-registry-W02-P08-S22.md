---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:4007aee4eddc316e4e171ba439ca78d83774fa34cb437607bc32723a30e874af'
step_id: 'S22'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Project modelo-owned facts without moving parameter files

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/facts/modelo_projections.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W02-P08-S22.md`
- `verify:` `uv run pytest -q src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/facts/modelo_projections.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py src/cadrumo/domain/calculations/registry/authority.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/calculations/registry/facts/modelo_projections.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py src/cadrumo/domain/calculations/registry/authority.py` -> `pass`
- `verify:` `uv run python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; a=bundled_authority(); print(sorted(k for k in a.catalogues.facts.facts if k.startswith(('declarations.m347','renta.maternity'))))"` -> `pass`
