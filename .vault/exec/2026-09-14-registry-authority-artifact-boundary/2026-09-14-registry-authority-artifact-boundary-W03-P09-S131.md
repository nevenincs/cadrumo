---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:f717cb2c7f1289ccdee99acaa4ec4bb4ffda35271e0a2cb9b6382bc7d9793f6b'
step_id: 'S131'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Extend the paired benchmark driver for independent workloads, full admission cost, incremental RSS and cache telemetry; run release measurements at checkpoint C

## Scope

- `dev/registry/benchmark_authority.py`

## Changes

- `M` `dev/registry/benchmark_authority.py`
- `verify:` `uv run --no-sync ruff check dev/registry/benchmark_authority.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/registry/benchmark_authority.py` -> `pass`

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
