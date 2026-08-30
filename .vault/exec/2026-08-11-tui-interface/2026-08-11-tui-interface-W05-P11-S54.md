---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:ffe9f2c419d62878b5f3d46b58f0a0f2b3f58d8b83012252a1012788583c73f3'
step_id: 'S54'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Render modelo.workspace.results for the current Workspace session and an explicitly selected read-only ModeloRevisionPick without mixing historical and current capability

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view/results.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/view/results.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_results.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/ -m "unit or integration" -n0 -q` -> `pass` (112 passed; the 2 failures are in `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`, peer-held and outside this Step)
