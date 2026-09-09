---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:206a23471318cbfed2c22dfa643be5b34e9feccf2dab919b5f1eb7fa6c2bc2cf'
step_id: 'S286'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unread workflow operation-instant context, getter, scope, export, and CAS wrapper while retaining the actual retry loop; run focused gates, classify unrelated envelope-schema reds, update cadence, and remeasure exact reachability.

## Scope

- `workflow persistence and focused persistence tests`

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

- `M` `src/cadrumo/application/workflow/persistence.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for operation-instant context/getter/scope -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` workflow persistence tests -> `8 passed, 3 peer-owned envelope-schema failures`
- `verify:` exact reachability -> `253 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

The focused persistence run still has three adapter-owned envelope-header validation failures: `written_at`, `payload`, and `encryption` are rejected as extra fields when loading rows written by the same suite. The removed operation-instant context does not participate in envelope serialization or validation; eight sibling persistence tests pass, and the same failures remain outside this Step's ownership.
