---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d41f6efb83c05920f306b38856207a74658e7dc4ba4b623e2bd7fdbc812e6128'
step_id: 'S333'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove synthetic Python packages and source-text policy checks from TUI visual inventory tests

## Scope

- `TUI visual inventory suite`
- `real artifact behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `dev/tui/tests/test_tui_visual_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q dev/tui/tests/test_tui_visual_inventory.py -m "not tui_render"` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
