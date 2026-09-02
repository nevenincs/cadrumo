---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:153ec6e4aa6b31da94fba22af67a27354e78c3c7b729c058c8a5a939f1130cb4'
step_id: 'S11'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---


# Harden public annotation resolution and forward-reference behavior

## Scope

- `src/cadrumo/application/modelo/workspace_manifest.py`

## Changes

- `M` `src/cadrumo/application/modelo/workspace_manifest.py`
- `verify:` `uv run --no-sync python -m py_compile src/cadrumo/application/modelo/workspace_manifest.py` -> `pass`

