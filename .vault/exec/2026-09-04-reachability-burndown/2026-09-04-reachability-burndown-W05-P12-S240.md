---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:58e42343050677e6fde91b86950ea6f4363df9c27e74c737bc3fc102eb1b6250'
step_id: 'S240'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

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
