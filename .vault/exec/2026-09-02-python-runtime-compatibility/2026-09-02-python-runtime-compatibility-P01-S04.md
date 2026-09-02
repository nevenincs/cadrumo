---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:186549e26b9c9b8f91852a4fcf673dcbd7c6ee0f3602a912f9d78c148f023edc'
step_id: 'S04'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Parse and validate the runtime inventory and emit GitHub matrix JSON

## Scope

- `dev/ci/python_runtime_matrix.py`

## Changes

- `A` `dev/ci/python_runtime_matrix.py`
- `verify:` `uv run --no-sync ruff check dev/ci/python_runtime_matrix.py; uv run --no-sync python -m dev.ci.python_runtime_matrix` -> `pass`
