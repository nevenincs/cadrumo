---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:6069a54eeee0b4ccf1f0f9f30997b5e4122dfb6367d058fa67908f8209c25784'
step_id: 'S241'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the deferred cross-layer import status ledger and its census-agreement tests; retain the executable import-linter layer contracts as the sole architecture authority.

## Scope

- `Deferred cross-layer import census test`
- `import-linter contracts and focused gate`
- `cadence reference`
- `and Step Record.`

## Changes

- `D` `src/cadrumo/tests/test_deferred_cross_layer_imports.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync lint-imports` -> `pass`
