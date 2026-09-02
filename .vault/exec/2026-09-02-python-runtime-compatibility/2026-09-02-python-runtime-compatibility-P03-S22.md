---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:39379eced247ecfe09952983cd9c25d0dba00ac762c6b441f445cb79b8796201'
step_id: 'S22'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---


# Verify smoke acceptance removes checkout imports and ambient executables

## Scope

- `dev/packaging/tests/test_smoke_core_env.py`

## Changes

- `M` `dev/packaging/tests/test_smoke_core_env.py`
- `verify:` `uv run --no-sync ruff check dev/packaging/tests/test_smoke_core_env.py; uv run --no-sync python -m py_compile dev/packaging/tests/test_smoke_core_env.py; uv run --no-sync pytest -q dev/packaging/tests/test_smoke_core_env.py -o addopts=''` -> `pass`
