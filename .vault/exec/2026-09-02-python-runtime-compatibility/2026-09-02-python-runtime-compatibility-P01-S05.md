---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c2bcdcb1b8896ec1c1b33790673d30d8bbf374e9919389559d8cfc09a88d2f09'
step_id: 'S05'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Add detector-teeth tests for runtime inventory gaps duplicates and invalid states

## Scope

- `dev/ci/tests/test_python_runtime_matrix.py`

## Changes

- `M` `dev/ci/python_runtime_matrix.py`
- `A` `dev/ci/tests/test_python_runtime_matrix.py`
- `verify:` `uv run --no-sync pytest -q dev/ci/tests/test_python_runtime_matrix.py; uv run --no-sync ruff check dev/ci/python_runtime_matrix.py dev/ci/tests/test_python_runtime_matrix.py` -> `pass`

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
