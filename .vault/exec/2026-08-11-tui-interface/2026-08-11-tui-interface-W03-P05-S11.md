---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:af520513b16a3495e2278162b22e46f101050fc2c8f9426dea3702f92d556074'
step_id: 'S11'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Compose the five-stage profile journey with only the active stage body expanded

## Scope

- `src/cadrumo/entrypoints/tui/profile/app.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/profile/app.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/profile/tests/test_profile_journey.py -m integration` -> `pass` (5 passed)
