---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6fd4add93a3f4fd8982cccf7d537d4d19cd4ac9958bd4c5a639082ce8143c917'
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
