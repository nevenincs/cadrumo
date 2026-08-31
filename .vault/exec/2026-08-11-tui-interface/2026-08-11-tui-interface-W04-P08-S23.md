---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:59aa9acb4a48986399f0fa8cbcfd0b7eb6006a15d7f28631f38dcaa028207bc0'
step_id: 'S23'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Prove guided flows consume application-owned questions and decisions without embedding flow semantics

## Scope

- `src/cadrumo/entrypoints/tui/flows/tests/test_guided_flows.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/flows/tests/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/flows/tests/test_guided_flows.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/flows/tests/test_guided_flows.py -q -m unit` -> `pass` (4 passed)
