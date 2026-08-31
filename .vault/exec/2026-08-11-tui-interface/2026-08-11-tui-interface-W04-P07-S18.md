---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6951e0e8201e758371e6335ab0790146bf15b90cb94f5603857826841f73edd9'
step_id: 'S18'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Complete login and profile-picker presentation without moving authentication policy into the TUI

## Scope

- `src/cadrumo/entrypoints/tui/secret/login.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/secret/login.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/ --collect-only -q` -> `pass` (0 errors)

## Notes

Landed as part of the single atomic `relocation:secret_screens` commit (`38349eee3d`), which also covers S17 and S19.
