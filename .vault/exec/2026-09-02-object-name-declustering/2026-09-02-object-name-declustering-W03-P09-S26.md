---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:25f3cc567011660110b874c49faa2425995f9f3d3d9b1bb8d5ae5db4a56a425f'
step_id: 'S26'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Apply the reviewed pilot receipt and verify live reduction

## Scope

- `dev/registry/generate_result_disposition_fragments.py`
- `dev/registry/result_disposition_fragment_generator.py`

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
