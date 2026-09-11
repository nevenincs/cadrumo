---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:ed5f829415ff664f927746fa8ba814d1d3d69fc9ad901240fc0b430fe34782ab'
step_id: 'S53'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Expose per-target generated-tree currentness as a read-only public primitive

## Scope

- `dev/registry/pipeline/cli.py`

## Changes

- `M` `dev/registry/pipeline/cli.py`
- `M` `justfile`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline target-current 296 2024-y-siguientes aeat-dr-296-2024 2024 0A` -> `pass`
