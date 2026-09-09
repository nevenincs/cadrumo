---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:2b65176f90ce27fee48f71f1712f3bec0e37c6a8f3865f573023e5fb3a191957'
step_id: 'S333'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
