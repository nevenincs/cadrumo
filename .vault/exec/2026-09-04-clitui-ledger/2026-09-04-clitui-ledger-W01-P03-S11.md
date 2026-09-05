---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:6d5fbaf497faf3403b10a9607fab8da4c8056c7f38917cb5b8ffe684eeb861ce'
step_id: 'S11'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Mark every TUI-applicable union and matrix row held until G3, retain component-only versus installed distinctions, and fail closed on hold drift or additions

## Scope

- `dev/quality/clitui_ledger_capability_matrix.py`
- `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
- `.vault/reference/2026-09-04-clitui-ledger-reference.md`

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

- `M` `dev/quality/clitui_ledger_capability_matrix.py`
- `M` `dev/quality/tests/test_clitui_ledger_capability_matrix.py`
- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P03-S11.md`
