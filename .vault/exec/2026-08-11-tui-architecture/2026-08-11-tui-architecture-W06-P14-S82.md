---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:758345633c6d4da6c812b40a2adb124dc5b11c7ff31bd043ef9a87e8866aa365'
step_id: 'S82'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Replace representative wizard TUI imports with frontend-neutral application flow contracts

## Scope

- `src/cadrumo/entrypoints/cli/_config/_apoderado.py`

## Changes

M .vault/plan/2026-08-11-tui-architecture-plan.md
- `verify:` whole-tree TUI boundary sweep over the cited module -> `0 violations`

## Notes

Verified rather than implemented: the surface is already at the row's terminal
state, and the whole-tree TUI boundary sweep is what holds it there. That sweep
scans every shipped file and permits exactly three CLI launch seams, each keyed
by enclosing function; none of them is this module, so a reintroduced import
here reds the gate by name.

The same plan-versus-code discrepancy as its descendant sibling: the
representative wizard's TUI imports are gone, but the surface is a declarative
Typer command rather than a consumer of an application flow contract, and it
prompts for nothing. No wizard remains to route through the flow engine.
