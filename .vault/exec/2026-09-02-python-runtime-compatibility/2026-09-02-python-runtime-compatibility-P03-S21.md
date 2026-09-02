---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:aa43a6403f8fb0fd854c77828e23942beb4ea5a10d4c766f26e5cbeec310f414'
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
