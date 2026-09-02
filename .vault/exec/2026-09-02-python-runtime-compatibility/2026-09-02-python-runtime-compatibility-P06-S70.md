---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:faf058ed98ffe7a53b41791375e69f263d50adb5fb816f31c6e605374bfc4f21'
step_id: 'S70'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Close binary compatibility dependency resolution to the sealed runtime wheelhouse

## Scope

- `dev/ci/python_runtime_compatibility.py`

## Changes

- `M` `dev/ci/python_runtime_compatibility.py`
- `M` `dev/ci/tests/test_python_runtime_compatibility.py`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility.py -o addopts='' && uv run --no-sync ruff check dev/ci/python_runtime_compatibility.py dev/ci/tests/test_python_runtime_compatibility.py` -> `pass`
