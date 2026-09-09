---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:53f23173614ca7950cc6e0620cb029c0247e1a232e2fd386ca5592b6b31eb6d3'
step_id: 'S02'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Define typed queries and provenance-bearing resolved results

## Scope

- `src/cadrumo/domain/calculations/registry/facts/resolution.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/facts/resolution.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/__init__.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_resolution.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P01-S02.md`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_resolution.py -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/facts/resolution.py src/cadrumo/domain/calculations/registry/facts/tests/test_resolution.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/facts/resolution.py src/cadrumo/domain/calculations/registry/facts/tests/test_resolution.py` -> `pass`
