---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:168ce93269ea9a6541466be23017e66598afaee7122ab8e3d2dbed51f53499d9'
step_id: 'S21'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---


# Reuse installed-wheel isolation for selected target interpreters

## Scope

- `dev/packaging/_smoke_common.py`

## Changes

- `M` `dev/packaging/_smoke_common.py`
- `verify:` `uv run --no-sync ruff check dev/packaging/_smoke_common.py; uv run --no-sync python -m py_compile dev/packaging/_smoke_common.py` -> `pass`
