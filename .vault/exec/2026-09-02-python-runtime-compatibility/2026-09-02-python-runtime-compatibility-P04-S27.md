---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:0fc71b15393fdaf79b9db7f07188a0c2f19460698eae6fdbc7cba8f231013bed'
step_id: 'S27'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---
# Verify workflow Python calls use repository module entry points

## Scope

- `dev/ci/tests/test_workflow_tool_invocation.py`

## Changes

- `M` `dev/ci/tests/test_workflow_tool_invocation.py`
- `verify:` `uv run --no-sync pytest -q -o addopts='' dev/ci/tests/test_workflow_tool_invocation.py; uv run --no-sync ruff check dev/ci/tests/test_workflow_tool_invocation.py` -> `pass`
