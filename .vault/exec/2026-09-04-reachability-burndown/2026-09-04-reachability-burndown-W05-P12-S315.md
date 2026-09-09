---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:494aa541c97312525c18fae939b3ffcfcc160e2e249dbfdf47abdf549981dec7'
step_id: 'S315'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the live-filename magic-banner lint and embedded test modules

## Scope

- `filename marker lint`
- `live test collection`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_filename_live_marker_lint.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest --collect-only -q -n0 -o addopts='' src/cadrumo/application/live/tests` -> `pass`
