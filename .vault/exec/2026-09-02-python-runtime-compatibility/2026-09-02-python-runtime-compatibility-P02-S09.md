---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:d52d69257f8c52ea86a666d050cb9e094e79727df0dc5de4d2019e5f3b193a7c'
step_id: 'S09'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Add an AST compatibility census for removed and deprecated Python APIs

## Scope

- `dev/quality/python_compatibility_scan.py`

## Changes

- `M` `dev/quality/python_compatibility_scan.py`
- `verify:` `uv run --no-sync ruff check dev/quality/python_compatibility_scan.py; .venv\Scripts\python.exe -m py_compile dev/quality/python_compatibility_scan.py; .venv\Scripts\python.exe -m dev.quality.python_compatibility_scan` -> `pass`
