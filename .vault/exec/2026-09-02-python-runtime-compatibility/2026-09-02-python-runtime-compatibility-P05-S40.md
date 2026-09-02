---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:2a956d07341b1911a3baa9882b8b9dbe9fac231bae8051bb817f26fb6a0f8408'
step_id: 'S40'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Document final-runtime promotion and classifier evidence

## Scope

- `RELEASING.md`

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

- `M` `RELEASING.md`
- `verify:` `uv run --no-sync python -c 'from pathlib import Path; text=Path("RELEASING.md").read_text(encoding="utf-8"); required=("dev/ci/python-runtime-matrix.json",".python-version","source-vs-binary","sealed-artifact","classifier_eligible: false","just python-compatibility","per-runtime rebuild"); missing=[item for item in required if item not in text]; assert not missing, missing; print("release-runtime-promotion docs: pass")'` -> `pass`
