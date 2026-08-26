---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:189fc731f951322de2b2ede05665d5b590b407fa6cd2be2b50ab5761c02f7aea'
step_id: 'S81'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace descendant wizard TUI imports with frontend-neutral application flow contracts

## Scope

- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`

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

Plan-versus-code discrepancy, recorded because the row's letter is not what
shipped. The row asks to replace the wizard's TUI imports with frontend-neutral
application flow contracts. The imports are gone, but the surface does not
consume a flow contract: it became a declarative Typer command with typed
options that emits an envelope, and it carries no interactive prompt at all.

There is therefore no wizard left to route through the flow engine, and the
row's intent -- a CLI surface that does not reach the TUI -- holds. Code wins.
