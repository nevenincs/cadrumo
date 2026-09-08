---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:cf1e05f29b344a77acf21f775ad0cba55905c9b4d4cd3b73dc5a9033d83798b2'
step_id: 'S282'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unreachable portable-profile bundle import facade and its sole-called repository/rebuild helpers, then burn the exposed test-only custody restore slice through application, port, adapter, persistence, and restore-only tests while retaining live export-policy behavior; update cadence and remeasure exact reachability.

## Scope

- `profile bundle and custody carry application/port/adapter surfaces and focused tests`

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

- `M` `src/cadrumo/application/user_profile/bundle.py`
- `M` `src/cadrumo/application/user_profile/custody_carry.py`
- `M` `src/cadrumo/application/user_profile/custody_ports.py`
- `M` `src/cadrumo/adapters/persistence/storage/profile_custody.py`
- `M` `src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py`
- `M` `src/cadrumo/application/user_profile/tests/test_custody_roundtrip.py`
- `D` `src/cadrumo/application/user_profile/tests/test_custody_restore_atomicity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for bundle/custody restore surfaces -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` retained custody export-policy test -> `1 passed`
- `verify:` live bundle export/validation imports -> `pass`
- `verify:` exact reachability -> `259 unused symbols, 31 unreachable modules, 0 orphaned tests`
