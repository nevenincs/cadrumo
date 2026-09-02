---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:bb57d384a6a7510643160c6a1f4c4f8d1a908b0a9c67fe003fcff6f69e4dfe9f'
step_id: 'S08'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Refresh the locked dependency graph after the direct LibCST declaration

## Scope

- `uv.lock`

## Changes

- `M` `uv.lock`
- `verify:` `uv lock --check` -> `pass`
- `verify:` `uv run --no-sync python -c "import libcst"` -> `pass`
- `verify:` `git diff --check -- uv.lock` -> `pass`
