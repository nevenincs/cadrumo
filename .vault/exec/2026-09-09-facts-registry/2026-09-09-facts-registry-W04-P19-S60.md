---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:af969e9efb853b00bded757a09a97f4c8b8d73937895a940b28dec43d2d2d689'
step_id: 'S60'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Run both dead-code audits and remove exact orphaned code and tests

## Scope

- `dev/audit/dead_code.py and dev/audit/unreachable_code.py`

## Changes

- `verify:` `uv run --no-sync python -m dev.audit.dead_code --full --json` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --full --json` -> `fail`

## Notes

The reachability audit reports a pre-existing general backlog but no exact facts-registry orphan. No deletion is safe or authorized from its heuristic candidates; retained IVA surfaces remain governed holds pending S81-S85.
