---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:68f7627db6ae4ad5a9de3ade531feb52a099978d76687aa52b5e213161cb930b'
step_id: 'S17'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Implement isolated source and binary compatibility probes with JSON evidence

## Scope

- `dev/ci/python_runtime_compatibility.py`

## Changes

- `A` `dev/ci/python_runtime_compatibility.py`
- `verify:` `uv run --no-sync ruff check dev/ci/python_runtime_compatibility.py; uv run --no-sync python -m py_compile dev/ci/python_runtime_compatibility.py` -> `pass`
