---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:85bc4d331a1ae5133fc465ba25c696c367d56b8da8e42be9f3623eb4242ce588'
step_id: 'S76'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove frontend-owned manager callbacks and consume registered operation APIs and application results only

## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`

## Changes

M .vault/plan/2026-08-11-tui-architecture-plan.md
- `verify:` TUI boundary sweep over all 67 cli/_config modules -> `0 violations`

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

Verified rather than implemented. The cited module no longer exists: a single
earlier change retired it along with the censo review UI surface, taking twelve
hundred lines of frontend-owned callbacks with it and reducing the dispatch
module to a hundred and thirty lines.

What remains is a CLI projection: the dispatcher wraps a wizard command with an
output-language activation and an error boundary, and reads its flow from the
core wizard catalogue. No frontend is constructed and no callback is owned here.

Plan-versus-code discrepancy, recorded because the row's second clause is not
literally what shipped. The row asks that the surface consume registered
operation APIs and application results only; the dispatcher consumes a core
wizard-catalogue flow instead. With the callbacks module deleted there is no
subject left for that clause, and the frontend-neutrality it exists to secure
holds. Code wins.

The whole `cli/_config` surface is swept by the TUI boundary detector, so a
reintroduced frontend reach in any of its sixty-seven modules reds by name.
