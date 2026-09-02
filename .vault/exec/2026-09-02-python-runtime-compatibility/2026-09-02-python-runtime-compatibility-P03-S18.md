---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a08bebcc31f69de9595b88c6eae5d6c266bc2a96478cead58c65d9876197b09d'
step_id: 'S18'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Test mode separation lock binding digest binding and missing-wheel refusal

## Scope

- `dev/ci/tests/test_python_runtime_compatibility.py`

## Changes

- `A` `dev/ci/tests/test_python_runtime_compatibility.py`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility.py -o addopts=''`; `uv run --no-sync ruff check dev/ci/python_runtime_compatibility.py dev/ci/tests/test_python_runtime_compatibility.py` -> `pass`
