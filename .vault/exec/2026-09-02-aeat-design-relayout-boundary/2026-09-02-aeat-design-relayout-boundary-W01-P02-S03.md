---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:ec7ef30864281ed337cdf9341804a8fc8941226346547af5a3fc87b64c87fd42'
step_id: 'S03'
related:
  - "[[2026-09-02-modelo-200-semantic-crosswalk-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Retire historic-payload restoration as authority-producing behavior while retaining proposal-only diagnostics

## Scope

- `dev/registry/analysis/m200_2024_restoration_candidates.py`

## Changes

- `M` `dev/registry/analysis/m200_2024_restoration_candidates.py`
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/m200_2024_restoration_candidates.py` -> `pass`

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
