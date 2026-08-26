---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:e3d198e75cb80e03687e9204febc2971222f16ec77fe96698254ccaaeaac3c6f'
step_id: 'S16'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Prove acquisition is never implicit and reconciliation persists only accepted decisions through public contracts

## Scope

- `src/cadrumo/entrypoints/tui/profile/tests/test_sync_review.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/profile/tests/test_sync_review.py`
- `M` `src/cadrumo/entrypoints/tui/profile/tests/test_census_sync_review.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/profile/ -q -m "unit or integration"` -> `pass` (21 passed)

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

Found and fixed a real production defect while writing these proofs: CensalFieldReviewScreen's apply-all button called SelectionList.select/deselect with a loop index where the API requires the option's own value, so reverting to the suggested selection was a silent no-op. Fixed in sync_review.py (S15's file) and regression-tested here.
