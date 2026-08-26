---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:9494030b25c2e02383f651dc9dd21e5a7e78ac467e4d480d69f5d2eee616b572'
step_id: 'S23'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Prove guided flows consume application-owned questions and decisions without embedding flow semantics

## Scope

- `src/cadrumo/entrypoints/tui/flows/tests/test_guided_flows.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/flows/tests/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/flows/tests/test_guided_flows.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/flows/tests/test_guided_flows.py -q -m unit` -> `pass` (4 passed)

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
