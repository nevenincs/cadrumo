---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:f596428b05efe10f9f9bebea361dfe2a0bb65d515fef201cc0b03192ad5e5a52'
step_id: 'S281'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the temporal-selection source scanner, path-keyed sanctioned-site metastate, and Python-source string tests; retain and run the direct temporal behavior suite, update cadence, and remeasure exact reachability.

## Scope

- `temporal registry tests and signal-burndown cadence`

## Changes

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

- `M` `src/cadrumo/domain/calculations/registry/tests/test_temporal.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for the sanctioned-site list, AST scanner helpers, and embedded `select_revision` source strings -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` direct temporal behavior suite -> `19 passed`
- `verify:` exact reachability -> `260 unused symbols, 31 unreachable modules, 0 orphaned tests`
