---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:3633d865aeae578d5c71a587af3a4bfd5895885eaf8b52cb1960b1547d68c563'
step_id: 'S81'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Replace descendant wizard TUI imports with frontend-neutral application flow contracts

## Scope

- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`

## Changes

M .vault/plan/2026-08-11-tui-architecture-plan.md
- `verify:` whole-tree TUI boundary sweep over the cited module -> `0 violations`

## Notes

Verified rather than implemented: the surface is already at the row's terminal
state, and the whole-tree TUI boundary sweep is what holds it there. That sweep
scans every shipped file and permits exactly three CLI launch seams, each keyed
by enclosing function; none of them is this module, so a reintroduced import
here reds the gate by name.

Plan-versus-code discrepancy, recorded because the row's letter is not what
shipped. The row asks to replace the wizard's TUI imports with frontend-neutral
application flow contracts. The imports are gone, but the surface does not
consume a flow contract: it became a declarative Typer command with typed
options that emits an envelope, and it carries no interactive prompt at all.

There is therefore no wizard left to route through the flow engine, and the
row's intent -- a CLI surface that does not reach the TUI -- holds. Code wins.
