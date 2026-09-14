---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:9187ce39d4537dbec7d1d3944efd1fdd4028d9a9a93305a8adf9dc5f4357077e'
step_id: 'S126'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Implement one publication acceptance suite for Windows held-reader cutover, database tamper, collisions and deferred cleanup; run it at checkpoint C

## Scope

- `dev/registry/tests/test_authority_generation_publication.py`

## Changes

- `A` `dev/registry/tests/test_authority_generation_publication.py`
- `M` `dev/registry/pipeline/authority_publication.py`
- `verify:` `checkpoint A focused source/enrollment and component selection` -> `pass`

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
