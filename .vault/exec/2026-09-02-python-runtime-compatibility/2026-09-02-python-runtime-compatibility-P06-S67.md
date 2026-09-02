---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:b46d6cacd7807c6bf73eb49333dbe718aa47ae6db62db518b18999bae33d4112'
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
