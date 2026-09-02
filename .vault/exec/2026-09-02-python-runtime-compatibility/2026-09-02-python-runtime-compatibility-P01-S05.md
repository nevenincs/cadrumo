---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:089284065118e16b20ac26dc895f42bf198ca95545328e686bc95bea32a0e167'
step_id: 'S05'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Add detector-teeth tests for runtime inventory gaps duplicates and invalid states

## Scope

- `dev/ci/tests/test_python_runtime_matrix.py`

## Changes

- `M` `dev/ci/python_runtime_matrix.py`
- `A` `dev/ci/tests/test_python_runtime_matrix.py`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_matrix.py; uv run --no-sync ruff check dev/ci/python_runtime_matrix.py dev/ci/tests/test_python_runtime_matrix.py` -> `pass`
