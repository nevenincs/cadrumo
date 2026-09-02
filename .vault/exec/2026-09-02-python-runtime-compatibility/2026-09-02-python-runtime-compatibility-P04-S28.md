---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:66a2b214a16607efea74366cff658c7bad0ba1ec5b80f1b1d920d09c9d678150'
step_id: 'S28'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---
# Preserve protected packaging-smoke single-build behavior

## Scope

- `dev/packaging/tests/test_packaging_smoke_workflow.py`

## Changes

- `M` `dev/packaging/tests/test_packaging_smoke_workflow.py`
- `verify:` `uv run --no-sync pytest -q -o addopts='' dev/packaging/tests/test_packaging_smoke_workflow.py; uv run --no-sync ruff check dev/packaging/tests/test_packaging_smoke_workflow.py` -> `pass`
