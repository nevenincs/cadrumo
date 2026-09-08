---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:a1f52952e647dc1f5ba3e5a239b278995ca58d6fcf23e8c4020d15b940422f4d'
step_id: 'S267'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
