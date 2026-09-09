---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:e1a70bee8035804a252cb47109c0c458f232f510423cf61a534726351a9812fd'
step_id: 'S332'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove hardcoded harness-source parsing and self-source import checks from TUI theme coverage

## Scope

- `TUI frame theme tests`
- `direct manifest and CLI behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `dev/tui/tests/test_tui_frame_theme_ownership.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q dev/tui/tests/test_tui_frame_theme_ownership.py dev/tui/tests/test_tui_viewport_geometry_ownership.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
