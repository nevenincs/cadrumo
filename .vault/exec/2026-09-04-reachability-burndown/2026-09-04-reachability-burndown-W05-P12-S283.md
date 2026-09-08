---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:904fb1a0f80d957ef9f5fc58e7a50e6ce982e4f511ad752eb51950cc576070bc'
step_id: 'S283'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the zero-caller speculative censo unadopted-evidence projector, its fixed field/namespace census, parser adapter, exports, and development-staging prose while retaining the live reviewed-censal divergence owner; run focused integration gates, update cadence, and remeasure exact reachability.

## Scope

- `cotejo apply production surface and reviewed-censal integration tests`

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

- `M` `src/cadrumo/application/user_profile/cotejo_apply.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for speculative censo projector/census/namespace symbols -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` reviewed-censal and schema-judgement integration tests -> `14 passed`
- `verify:` exact reachability -> `258 unused symbols, 31 unreachable modules, 0 orphaned tests`
