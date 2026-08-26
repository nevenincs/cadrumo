---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:d005830d61d43c4f8da4b026edb12392201adc831de04660ccd5fe044b17e15c'
step_id: 'S82'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace representative wizard TUI imports with frontend-neutral application flow contracts

## Scope

- `src/cadrumo/entrypoints/cli/_config/_apoderado.py`

## Changes

M .vault/plan/2026-08-11-tui-architecture-plan.md
- `verify:` whole-tree TUI boundary sweep over the cited module -> `0 violations`

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

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
