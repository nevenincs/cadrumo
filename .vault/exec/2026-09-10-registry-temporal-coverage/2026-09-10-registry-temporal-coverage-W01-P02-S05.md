---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b69cabf2def2a7245fbe64c3d01f9e9ba418775f1085fb0f36740551fff7417a'
step_id: 'S05'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# Expose provenance classification through the validated authority without a second resolver path

## Scope

- `src/cadrumo/domain/calculations/registry/authority.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority"` -> `pass`
