---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:f6ce5daae3311421282abad4f10a27caf8cf279b910dc4e98df8989b57d41410'
step_id: 'S209'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only load_default_filing_profile convenience bridge and its export/documentation from production filing runtime, and make the cross-surface profile-bucket test compose the canonical workflow-state, active-profile, and filing-profile projection owners directly while retaining their live behavior and single-bucket identity proof.

## Scope

- `Filing runtime and cross-surface workflow test`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/application/filing/runtime.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/filing/runtime.py src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m "" --basetemp <isolated-workspace-temp> src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py::test_profile_create_set_deadlines_and_filing_runtime_share_profile_bucket` -> `pass` (1 passed)
- `verify:` `rg -n "load_default_filing_profile" src/cadrumo --glob '*.py'` -> `pass` (no matches)
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `findings` (318 exact unused symbols; target absent)

## Notes

The exact unused-symbol count fell from 319 immediately before S209 to 318 after removal of the convenience bridge; the live graph otherwise remained at 65 unreachable modules, 18 orphaned tests, and 2028/2094 shipped modules reachable.
