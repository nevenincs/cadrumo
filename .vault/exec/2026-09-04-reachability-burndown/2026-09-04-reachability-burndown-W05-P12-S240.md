---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:0f9cf84e68d663f8d29d0fa39d573b79cf4b23d47d61364fe5e380e24ccf8e46'
step_id: 'S240'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the _UNADJUDICATED_REPEATED_SLOTS development-status census and its mirror/staleness tests; retain the derived corpus anchor, split amount/date reconstruction, optional-slot, and planted-reversion renderer proofs.

## Scope

- `Fixed-width export split-part rendering tests`
- `exact derived corpus`
- `focused renderer gate`
- `cadence reference`
- `and Step Record.`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_export_split_part_rendering.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/tests/test_export_split_part_rendering.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s240 src/cadrumo/domain/calculations/registry/tests/test_export_split_part_rendering.py` -> `pass`
