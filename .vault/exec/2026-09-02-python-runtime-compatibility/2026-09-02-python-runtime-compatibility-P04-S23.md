---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:b0c61b447cca1831c1233fbe4c892c6eb6c71d8e536334b915dbfbcc6b885597'
step_id: 'S23'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---
# Add stable and next source and binary compatibility matrix jobs

## Scope

- `.github/workflows/python-runtime-compatibility.yml`

## Changes

- `A` `.github/workflows/python-runtime-compatibility.yml`
- `verify:` `uv run --no-sync pytest -q -o addopts='' dev/ci/tests/test_python_runtime_compatibility_workflow.py; uv run --no-sync ruff check dev/ci/tests/test_python_runtime_compatibility_workflow.py` -> `pass`
