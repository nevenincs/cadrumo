---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:e21f2c064ab28ba9eef1310f3216cce22e227d6d6ff9415f5494aaa46b78570c'
step_id: 'S17'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Complete reusable masked credential and password-entry presentation over the receipt-named public EphemeralSecretSubmission facade

## Scope

- `src/cadrumo/entrypoints/tui/secret/credentials.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/secret/credentials.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/ --collect-only -q` -> `pass` (0 errors)

## Notes

Landed as part of the single atomic `relocation:secret_screens` commit (`38349eee3d`), which also covers S18 and S19 -- the split, the delete of `app.py`, and all 10 consumer updates share one commit per `aeat-architecture-boundaries`.
