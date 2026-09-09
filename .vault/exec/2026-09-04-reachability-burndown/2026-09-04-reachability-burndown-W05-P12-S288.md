---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:1ff53eb40f9d15d1160b11e4e2aa24e31de6b3fb8583397862310a6f5add4a07'
step_id: 'S288'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-only workflow declaration-pointer state cluster—persisted field, model, validators, key builder, updater, exports, serialization fixture residue, and dedicated tests—while retaining live filing repositories and encrypted workflow-state behavior; run focused gates, update cadence, and remeasure exact reachability.

## Scope

- `workflow state models and state-persistence tests`

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

- `M` `src/cadrumo/application/workflow/state_models.py`
- `M` `src/cadrumo/application/workflow/tests/test_state_persistence_roundtrip.py`
- `D` `src/cadrumo/application/workflow/tests/test_declaration_key.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for workflow declaration-pointer vocabulary -> `no relevant production matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` encrypted workflow-state roundtrip tests -> `2 passed`
- `verify:` exact reachability -> `250 unused symbols, 31 unreachable modules, 0 orphaned tests`
