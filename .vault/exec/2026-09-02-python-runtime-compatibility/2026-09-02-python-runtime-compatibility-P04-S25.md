---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:2c41e8b47e046521454b660b7c9703841a4835fd89dc569a92128083ca0e48a9'
step_id: 'S25'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---
# Permit only the dedicated runtime matrix while preserving exact-pin lanes

## Scope

- `dev/ci/tests/test_python_version_pin.py`

## Changes

- `M` `dev/ci/tests/test_python_version_pin.py`
- `verify:` `uv run --no-sync pytest -q -o addopts='' dev/ci/tests/test_python_version_pin.py; uv run --no-sync ruff check dev/ci/tests/test_python_version_pin.py` -> `pass`
