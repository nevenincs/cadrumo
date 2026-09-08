---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:9d79472043646917723df27bb4645ce767078ef2ddcd39d8cefe80940d2d0fec'
step_id: 'S223'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unused contradictory ProfileName production alias and its orphaned validator-only test; retain the live canonical ProfileLabel and profile schema-version owner, and correct test commentary to name the actual live profile-label contract without preserving the dead alias or its obsolete bound.

## Scope

- `Contribuyente constants module and orphan test`
- `live profile-label owner`
- `boundary-fault test commentary`
- `accepted profile lifecycle decisions`
- `exact reachability signal`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/domain/contribuyente/constants.py`
- `D` `src/cadrumo/domain/contribuyente/tests/test_constants.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_calculate_boundary_fault_attribution.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S223.md`
- `verify:` `rg -n "ProfileName" src/cadrumo dev --glob '*.py'` -> `pass (only distinct ProfileNameCollisionError matches)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/contribuyente/constants.py src/cadrumo/entrypoints/cli/tests/test_calculate_boundary_fault_attribution.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s223 src/cadrumo/domain/contribuyente/tests src/cadrumo/entrypoints/cli/tests/test_calculate_boundary_fault_attribution.py` -> `pass (466 passed, 4 deselected)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 60 unreachable modules, 307 exact unused symbols, 10 orphaned tests, 2029/2090 shipped modules reachable)`
