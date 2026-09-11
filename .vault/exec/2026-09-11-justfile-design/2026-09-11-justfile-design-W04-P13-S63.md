---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:7b19d57d33e617fd7c36e94f00bf18f2e76d05d3c662816e947074eeec07508f'
step_id: 'S63'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Replace the generic TUI review and harness pass-throughs with authority-consistent operations or demote them

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --show tui-review` -> `pass`

## Notes

- `uv run --no-sync python -m dev.tui.harness --help` -> `fail` (pre-existing import mismatch; no harness started)
