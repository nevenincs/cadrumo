---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:7170bf51dbddfebc979b2fcdf50c8ee98e331009398a1304eb967edc8a5a8c8d'
step_id: 'S284'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the zero-caller wizard persist-answers facade and its unreachable error/locale vocabulary while retaining the live command writer, shared mode type, projections, and patch owner; rename misleading serialization coverage, run focused gates, update cadence, and remeasure exact reachability.

## Scope

- `wizard persistence module`
- `focused tests`
- `and application locales`

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

- `M` `src/cadrumo/application/wizard/persistence.py`
- `M` `src/cadrumo/application/wizard/tests/test_setup_runtime.py`
- `M` `src/cadrumo/application/wizard/tests/test_persistence_canonical.py`
- `M` `src/cadrumo/locales/ca/application.yml`
- `M` `src/cadrumo/locales/en/application.yml`
- `M` `src/cadrumo/locales/es/application.yml`
- `M` `src/cadrumo/locales/hu/application.yml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for persist-answers facade/error vocabulary -> `no production matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` wizard persistence/runtime tests -> `36 passed`
- `verify:` exact reachability -> `257 unused symbols, 31 unreachable modules, 0 orphaned tests`
