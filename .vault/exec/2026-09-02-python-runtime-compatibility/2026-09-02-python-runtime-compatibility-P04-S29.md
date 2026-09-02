---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:f9931f8d53c1ebbf33da37036991e56a69a42a27849210ec01f6e1c780c1cf80'
step_id: 'S29'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---
# Preserve protected quick-packaging single-runtime behavior

## Scope

- `dev/packaging/tests/test_packaging_quick_workflow.py`

## Changes

- `M` `dev/packaging/tests/test_packaging_quick_workflow.py`
- `verify:` `uv run --no-sync pytest -q -o addopts='' dev/packaging/tests/test_packaging_quick_workflow.py; uv run --no-sync ruff check dev/packaging/tests/test_packaging_quick_workflow.py` -> `pass`
