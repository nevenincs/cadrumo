---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:e21f2c064ab28ba9eef1310f3216cce22e227d6d6ff9415f5494aaa46b78570c'
step_id: 'S17'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Complete reusable masked credential and password-entry presentation over the receipt-named public EphemeralSecretSubmission facade

## Scope

- `src/cadrumo/entrypoints/tui/secret/credentials.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/secret/credentials.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/ --collect-only -q` -> `pass` (0 errors)

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

Landed as part of the single atomic `relocation:secret_screens` commit (`38349eee3d`), which also covers S18 and S19 -- the split, the delete of `app.py`, and all 10 consumer updates share one commit per `aeat-architecture-boundaries`.
