---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:635bd4439650504f7cb0518cb2cc8e6c486dc712dfc22b93845491ec57b5190f'
step_id: 'S77'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove manager TUI construction and retain only CLI projection or frontend-neutral selection behavior

## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_frontend.py`

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

`_manager_frontend.py` constructs no frontend. It is fifty-six lines of parser
and capability projection, and its own docstring records the division: building
or presenting the full-screen frontend belongs to the TUI package, and the CLI
stays a line-mode projection over the application contracts.

Its two textual matches on "tui" are that docstring sentence and the string
`"tui"` in the routing metadata key set, which names a CLI flag. Neither is an
import, which is why the boundary detector reports the module clean.
