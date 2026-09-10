---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:d3e0f05772c9e36fa0cefbb2c9e1a350520ef294514d0c3010db1b3e7b77c0e4'
step_id: 'S10'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Verify companion-package inclusion and the manual operator surface across the supported horizon

## Scope

- `packaging/cadrumo_data_manuals`

## Changes

- `verify:` `uv run python -c "... ZipFile(...).namelist() ..."` -> `pass`
- `verify:` `uv run pytest dev/packaging/tests/test_cadrumo_data_distribution.py` -> `fail`

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

The real source-tree wheel contains the 2022 and 2023 Sociedades PDFs. The
tracked-artifact parity gate correctly refuses to pass until those newly
acquired corpus inputs are staged or committed; no index mutation was
authorised.
