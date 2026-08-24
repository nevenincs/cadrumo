---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:cdf761b3e8330b51e147ce26e772996da3424c69c4f31a6d286d7517187e2120'
step_id: 'S111'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove the graph-wide available-route fixed point, global-only option placement, implemented-route dispatch, and representative unimplemented refusals

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_global_tui_request.py`
- `src/cadrumo/entrypoints/cli/_config/tests`

## Description

- Pin the complete `AVAILABLE` key set as a graph-wide fixed point.
- Prove `--tui` is advertised only by the root.
- Exercise typed refusals and profile routing with real CLI and focused tests.

## Outcome

Completed. Global TUI integration passed 9 tests, focused config routing passed
14 tests, Ruff passed, and a real PTY opened profile registration.

## Notes

The live PTY was abandoned with Ctrl+Q and created no profile.
