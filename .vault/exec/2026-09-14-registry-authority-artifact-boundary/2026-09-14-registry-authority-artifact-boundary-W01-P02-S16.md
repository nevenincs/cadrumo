---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:b609c55571e965a204e9a24601357dc702fa4f95d6a17c3a1d79bc46c01ad351'
step_id: 'S16'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Run checkpoint A once on representative source/enrollment and encoded-candidate fixtures; freeze lane contracts and preserve a runnable paired JSON baseline before retiring old APIs

## Scope

- `dev/registry/tests`

## Changes

- `A` `dev/registry/benchmark_authority.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_authority_component_contract.py`
- `verify:` `checkpoint A: pytest focused selection` -> `pass` (41 passed)
- `verify:` `checkpoint A: ruff check focused selection` -> `pass`
- `verify:` `checkpoint A: ty check focused selection` -> `pass`

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
