---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:d41f9e5d43c341b35b2cd60fe57058a697827c7138f063f1dcfc1053ff32442f'
step_id: 'S65'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Run a focused behavioral test set under the selected target interpreter and bind its results to the compatibility verdict

## Scope

- `dev/ci/python_runtime_compatibility.py`

## Changes

- `M` `dev/ci/python_runtime_compatibility.py`
- `M` `dev/ci/tests/test_python_runtime_compatibility.py`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_compatibility.py` -> `pass`
