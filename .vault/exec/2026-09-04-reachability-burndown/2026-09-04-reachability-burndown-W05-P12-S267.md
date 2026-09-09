---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b360642d077e348558238d8c77c7ec47df682736c6fd9c0a70dc189be48b3faf'
step_id: 'S267'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only Playwright browser-root role declaration and its identity assertion because the live resolver already owns vendor cache path behavior and production does not consume the classification; keep resolver behavior and provisioning tests, correct prose, run focused provisioning gates, remeasure exact reachability, update cadence, and write the Step Record.

## Scope

- `provisioning browser-root role constant and identity test`
- `resolver prose and focused provisioning tests`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `M` `src/cadrumo/application/provisioning.py`
- `M` `src/cadrumo/application/tests/test_provisioning.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/provisioning.py src/cadrumo/application/tests/test_provisioning.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/tests/test_provisioning.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

All 14 live provisioning and resolver tests pass. Exact unused symbols improved from 278 to 277; 31 unreachable modules and zero orphaned tests remain.
