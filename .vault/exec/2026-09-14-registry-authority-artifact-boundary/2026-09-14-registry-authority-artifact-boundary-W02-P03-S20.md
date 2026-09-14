---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:f7ea62f657158b74449d408b6f624562cf86b572e1d5e72a39abd8facea45a61'
step_id: 'S20'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Implement accounted LRU retention and concurrent-load coalescing with oversize, failure, cycle and lease-retirement behavior

## Scope

- `src/cadrumo/domain/calculations/registry/authority_cache.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/authority_cache.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_authority_cache.py`
- `verify:` `uv run --no-sync pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_authority_cache.py -q` -> `pass`

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
