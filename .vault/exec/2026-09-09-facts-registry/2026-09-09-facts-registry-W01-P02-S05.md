---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:5d8c28c52a3eaa45d9c42abfb4959ada701446f70509e9bd2238104383a6de44'
step_id: 'S05'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Attach the fact catalogue to authority construction

## Scope

- `src/cadrumo/domain/calculations/registry/authority.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_authority_catalogue.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P02-S05.md`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_authority_catalogue.py -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/authority.py src/cadrumo/domain/calculations/registry/schema.py src/cadrumo/domain/calculations/registry/facts/schema.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_authority_catalogue.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/authority.py src/cadrumo/domain/calculations/registry/schema.py src/cadrumo/domain/calculations/registry/facts/schema.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_authority_catalogue.py` -> `pass`
