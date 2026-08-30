---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:e3162317071dc03df17a7844627f778ae142bdb4efa6535faea5b43e956cc6a0'
step_id: 'S53'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Render modelo.workspace.inputs from bounded section, scalar, and repeated-row facets with stable keys and explicit edit dispositions but no edit control before C3

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view/inputs.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/view/inputs.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_inputs.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/ -m "unit or integration" -n0 -q` -> `pass` (112 passed; the 2 failures are in `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`, peer-held and outside this Step)
