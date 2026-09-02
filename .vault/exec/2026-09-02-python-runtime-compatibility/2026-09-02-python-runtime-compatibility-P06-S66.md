---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:448c2783e37b44ff2412b4f6638fc35ef8c8f882ba8ddd9b71eb308cdc128458'
step_id: 'S66'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---


# Smoke the installed cadrumo-mcp entry point and import contract in every compatibility mode

## Scope

- `dev/ci/python_runtime_compatibility.py`

## Changes


- `M` `dev/ci/python_runtime_compatibility.py`
- `M` `dev/ci/tests/test_python_runtime_compatibility.py`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility.py` -> `pass`
