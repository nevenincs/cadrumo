---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:73aeab1e91fa4a2135f181c25f21f8038e50609148aef53e98eb6fa8a1179c98'
step_id: 'S50'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# Migrate the enumerated profile CLI/TUI schema consumers and fixtures to compiled authority access; remove raw-loader references

## Scope

- `src/cadrumo/entrypoints`

## Changes

- `M` `src/cadrumo/entrypoints/cli/common.py`
- `M` `src/cadrumo/entrypoints/cli/config/_complete_setup_cli.py`
- `M` `src/cadrumo/entrypoints/cli/config/_profile_inspect.py`
- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `verify:` `checkpoint B focused import census` -> `pass`
