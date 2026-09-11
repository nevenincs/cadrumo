---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:2c69aa30f94f12ceaa9d32f46c984a5d5590a4819094a2043a12054e8b4488ca'
step_id: 'S14'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Delegate the legacy render-check entry point to canonical target-currentness semantics pending caller migration

## Scope

- `dev/registry/pipeline/render_check.py`

## Changes

- `M` `dev/registry/pipeline/render_check.py`
- `M` `dev/registry/pipeline/cli.py`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline.render_check 296 2024-y-siguientes --check` -> `pass`
