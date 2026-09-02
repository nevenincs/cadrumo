---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:d74e7793b58fbe98fc00a6d4bcaa320958ac0d0978e8288a22732a87f5e6607b'
step_id: 'S24'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---
# Gate workflow inventory source mode separation skips warnings and digests

## Scope

- `dev/ci/tests/test_python_runtime_compatibility_workflow.py`

## Changes

- `A` `dev/ci/tests/test_python_runtime_compatibility_workflow.py`
- `verify:` `uv run --no-sync pytest -q -o addopts='' dev/ci/tests/test_python_runtime_compatibility_workflow.py; uv run --no-sync ruff check dev/ci/tests/test_python_runtime_compatibility_workflow.py` -> `pass`
