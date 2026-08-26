---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6a5158c663d35731b4142913b526881609836cc53849aaa83ec8da1203d3275c'
step_id: 'S77'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Remove manager TUI construction and retain only CLI projection or frontend-neutral selection behavior

## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_frontend.py`

## Changes

M .vault/plan/2026-08-11-tui-architecture-plan.md
- `verify:` whole-tree TUI boundary sweep over the cited module -> `0 violations`

## Notes

Verified rather than implemented: the surface is already at the row's terminal
state, and the whole-tree TUI boundary sweep is what holds it there. That sweep
scans every shipped file and permits exactly three CLI launch seams, each keyed
by enclosing function; none of them is this module, so a reintroduced import
here reds the gate by name.

`_manager_frontend.py` constructs no frontend. It is fifty-six lines of parser
and capability projection, and its own docstring records the division: building
or presenting the full-screen frontend belongs to the TUI package, and the CLI
stays a line-mode projection over the application contracts.

Its two textual matches on "tui" are that docstring sentence and the string
`"tui"` in the routing metadata key set, which names a CLI flag. Neither is an
import, which is why the boundary detector reports the module clean.
