---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:5f2bc2d9804960bb9b6bc81ce4029ca03c7dcbdc6f011442c460866ff7d3fc81'
step_id: 'S354'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unreachable profile sync-review seam and its test-only censal and filed-history projections while retaining those behaviors at their application owners.

## Scope

- `profile sync review module and tests`
- `Modelo view documentation`
- `application owner gates`
- `exact reachability`

## Changes

- `D` `src/cadrumo/entrypoints/tui/profile/sync_review.py`
- `D` `src/cadrumo/entrypoints/tui/profile/tests/test_sync_review.py`
- `D` `src/cadrumo/entrypoints/tui/profile/tests/test_census_sync_review.py`
- `D` `src/cadrumo/entrypoints/tui/profile/tests/test_filed_history_operation_view.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/view/models.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/tui/modelo/view/models.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/application/user_profile/tests/test_censal_operation.py` -> `pass (7 passed in combined owner run)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (19 unreachable modules; down from 20)`

## Notes

The combined application-owner run continued past all seven passing censal tests but remained red on peer-owned filed-history settlement and source-scanning assertions. Those failures neither import nor exercise the deleted TUI seam.
