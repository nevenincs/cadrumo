---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:92aa82686bdf93ed070e235f60ceff9469f3d3146cb3326ffa6539f422757549'
step_id: 'S15'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Render provenance current and proposed values conflicts and exact apply or reject reconciliation decisions

## Scope

- `src/cadrumo/entrypoints/tui/profile/sync_review.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/profile/sync_review.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/profile/tests/test_sync_review.py -q -m integration` -> `pass` (7 passed)
