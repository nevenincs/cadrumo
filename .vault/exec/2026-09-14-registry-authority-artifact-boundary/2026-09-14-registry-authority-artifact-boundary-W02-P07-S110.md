---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:af7e8a2d42095aa32b898c3f9de0042ee54eebcec6e9688b3fdd4b08c51f9a97'
step_id: 'S110'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Require draft filing coordinates in runtime, export and verification; use selected source/layout dependencies and preserve stale-draft refusal

## Scope

- `src/cadrumo/application/filing`

## Changes

- `M` `src/cadrumo/application/filing/runtime.py`
- `M` `src/cadrumo/application/filing/export.py`
- `M` `src/cadrumo/application/filing/export_verification.py`
- `M` `src/cadrumo/application/filing/tests/test_filing.py`
- `M` `src/cadrumo/application/filing/tests/test_runtime_profile_export_bindings.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/filing/tests/test_filing.py src/cadrumo/application/filing/tests/test_runtime_profile_export_bindings.py -q` -> `pass`

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
