---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:929b4d16569b2555f578fb9418124f9d0d04a8a6a3c0fb6fdd5a2c90d0a3f7fc'
step_id: 'S03'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Compile identity conflicts, absent targets, unknown files, stale derivatives, and broken bindings into diagnostics

## Scope

- `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/artifact_catalogue.py; uv run ruff format --check src/cadrumo/domain/calculations/registry/artifact_catalogue.py; uv run ty check src/cadrumo/domain/calculations/registry/artifact_catalogue.py` -> `pass`
