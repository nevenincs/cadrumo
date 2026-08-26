---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:14a34662e9c695b878e9b64b8c3230d64775841bd11ca58282c13453be1c0412'
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
