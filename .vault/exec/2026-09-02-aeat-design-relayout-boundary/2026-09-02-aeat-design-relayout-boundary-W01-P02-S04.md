---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:f4e0840b893d007c554d06eb914441a3ba6fc906fe1a26b5443692dc85e342be'
step_id: 'S04'
related:
  - "[[2026-09-02-modelo-200-semantic-crosswalk-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Detect target-description, semantic-role, legal-reference, and source-SHA mutations at the historic-restoration boundary

## Scope

- `dev/registry/tests/test_m200_2024_restoration_candidates.py`

## Changes

- `M` `dev/registry/tests/test_m200_2024_restoration_candidates.py`
- `verify:` `uv run --no-sync pytest -q -n 0 dev/registry/tests/test_m200_2024_restoration_candidates.py` -> `pass`

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
