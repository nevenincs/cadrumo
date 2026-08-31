---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:77a6e661aad5a6a4c6f61be1c634656aeff82faa4186d1e992b449f0ab0e6b40'
step_id: 'S68'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement census local-versus-persisted field review with suggested intent, per-field selection, apply all, reject, and stale-proposal display

## Scope

- `src/cadrumo/entrypoints/tui/profile/sync_review.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/profile/sync_review.py`
- `verify:` `pytest src/cadrumo/entrypoints/tui/profile/tests/test_census_sync_review.py -m integration` -> `pass` (6 passed)
