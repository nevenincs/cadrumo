---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:af482b242cc6eea3de13d157c85593b9d5ca8d8afeec36741da5b5eedbd429b2'
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
