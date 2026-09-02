---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c97b2863a96639ffc7c34f1ce7d189f0efeb25a950446ac698f97e3ba9a54dea'
step_id: 'S67'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---


# Wire the future-directive AST policy into the blocking compatibility workflow

## Scope

- `.github/workflows/python-runtime-compatibility.yml`

## Changes


- `M` `.github/workflows/python-runtime-compatibility.yml`
- `M` `dev/ci/tests/test_python_runtime_compatibility_workflow.py`
- `verify:` `uv run --no-sync pytest -q -m integration dev/ci/tests/test_python_runtime_compatibility_workflow.py` -> `pass`
