---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:90c74d2a29e2417a727e66db525bd319bc88ded09f83f1ccccb9804b0de689ce'
step_id: 'S285'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the zero-caller workflow draft/submission adapters and private bridge, then burn the exposed test-only default-engine factory, missing-adapter errors/locales, hardened-error census rows, and factory tests while retaining the live deadline adapter; run focused gates, update cadence, and remeasure exact reachability.

## Scope

- `workflow adapters`
- `adapter tests`
- `hardened locale test`
- `submission prose`
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

- `M` `src/cadrumo/application/workflow/adapters.py`
- `D` `src/cadrumo/application/workflow/tests/test_adapters.py`
- `M` `src/cadrumo/domain/submission/engine.py`
- `M` `src/cadrumo/core/tests/test_locale_coverage_hardened_errors.py`
- `M` `src/cadrumo/locales/ca/application.yml`
- `M` `src/cadrumo/locales/en/application.yml`
- `M` `src/cadrumo/locales/es/application.yml`
- `M` `src/cadrumo/locales/hu/application.yml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for dead adapter/factory/error vocabulary -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` workflow engine and hardened-locale tests -> `10 passed`
- `verify:` exact reachability -> `254 unused symbols, 31 unreachable modules, 0 orphaned tests`
