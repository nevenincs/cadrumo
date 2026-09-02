---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:eb6940877e32502722a1ab2d3791bb29bb9526b98b0c03fc70793b8e978b208c'
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
- `verify:` `same-commit matrix at ea2f347ba22a5d566f18f8c97a995c22348eb3d9 with cohort d57b1de3c709...: source CPython 3.13.14, 3.14.6, 3.15.0b4; sealed offline binary CPython 3.13.14 and 3.14.6` -> `pass`
