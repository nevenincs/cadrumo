---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:2597ffc4ffa855e7d985121c266dfd9df02939bde77dfc290179e9cbe301a9cd'
step_id: 'S51'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Implement ModeloWorkspaceReadSession and the read controller with exact version admission, baseline-pinned facet traversal, bounded paging, locale-only refresh proof, and whole-session stale invalidation

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view/controller.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/view/controller.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_read_session.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/ -m "unit or integration" -n0 -q` -> `pass` (112 passed; the 2 failures are in `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`, peer-held and outside this Step)
