---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:37616407c7464d9bd65a60fb0078cc162cef7da8219a29c597c136855966518c'
step_id: 'S58'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Invoke clean release-cohort construction through its package module

## Scope

- `dev/packaging/release_cohort.py`

## Changes

- `M` `dev/packaging/release_cohort.py`
- `verify:` `uv run --no-sync pytest -q -o addopts='' dev/packaging/tests/test_release_cohort.py; uv run --no-sync ruff check dev/packaging/release_cohort.py dev/packaging/tests/test_release_cohort.py; uv run --no-sync python -m dev.packaging.release_cohort --help` -> `pass`

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
