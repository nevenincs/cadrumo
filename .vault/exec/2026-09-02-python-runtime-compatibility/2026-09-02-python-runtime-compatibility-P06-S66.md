---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:2c771d932f381a3ecd5d6e8fb6b857c4e5bfa6be33edf3ed45fa7836c0746d5a'
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
