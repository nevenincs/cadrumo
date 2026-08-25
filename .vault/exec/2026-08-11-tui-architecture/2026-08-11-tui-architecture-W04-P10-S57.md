---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:840d1c2110be22fc3efa03888160896d43698f109bf4f94f91efdc1873aa7854'
step_id: 'S57'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Relocate TUI-owned pilot, replay, screenshot, and terminal-surface tooling

## Scope

- `src/cadrumo/entrypoints/tui/devtools`

## Description

- Hard-move fixture, frame, journal, replay, and surface tooling from underscore-private modules to public defining modules.
- Rewrite every devtool consumer to import the public defining module directly.
- Delete all five former modules without shims, aliases, re-exports, or compatibility paths.
- Keep the devtools package namespace inert.
- Add a narrow real-behavior test that persists and restores a journal, replays the registration compositor, and exports its SVG frame.

## Outcome

TUI pilot, replay, screenshot, journal, and terminal-surface tooling now has one public canonical home per concern under `entrypoints.tui.devtools`. Exact source and development searches find no former module path or relative import, and AST inspection finds no duplicate definitions.

The installed module command lists the real surfaces. Ruff and formatting pass; structural ownership and real public-home integration tests pass two cases. Independent review approved the hard move with no findings.

## Notes

The package initializer remains intentionally inert. Consumers import `fixture`, `frame`, `journal`, `replay`, or `surfaces` directly; no convenience facade was introduced.

Temporal correction: the original execution record in `eb732c9db90` described the intended public-module state before that state was reachable in its own tree. The hard move became reachable in successor `be01c4b0be2`. The current-tree exact census, command smoke, behavior test, and independent review establish the outcome now; the earlier record alone is not implementation evidence.
