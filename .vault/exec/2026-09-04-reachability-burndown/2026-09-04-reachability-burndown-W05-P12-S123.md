---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:d8624e0b91bbcb30c13674a6063786b87e6251e3d0c0f936f5cf675fe4f52cfb'
step_id: 'S123'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---
# Delete the two unregistered Home prototype screens and their test-only implementation, since production ships the chosen Home screen and development candidates have no source-tree owner

## Scope

- `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`

## Changes

- `D` `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`
- `D` `src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/tests/test_every_source_file_parses.py dev/tui/tests/test_tui_visual_inventory.py dev/tui/tests/test_tui_surface_identity_resolution.py` -> `55 passed, 1 skipped`
- `verify:` `just check-tui-render-coverage` -> `expected red: reduced from 10 to 8 concrete interfaces`
