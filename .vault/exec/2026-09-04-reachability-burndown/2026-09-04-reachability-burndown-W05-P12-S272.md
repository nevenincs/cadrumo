---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:91641417650851183e33c08a7dcb129130d0d6ad968b64f68280db2059646d31'
step_id: 'S272'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the production repair-policy command-surface catalog and its self-referential coverage suite because no runtime consumer uses the catalog; preserve and verify the live bucket repair session, update cadence, and remeasure exact reachability.

## Scope

- `src/cadrumo/application/repair_integrity.py and src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`

## Changes

- `M` `src/cadrumo/application/repair_integrity.py`
- `D` `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact symbol search for the catalog models, builder, and dedicated suite -> `no matches`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/tests/test_diagnostics.py -k "repair or quarantine"` -> `10 passed, 29 deselected`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail (live findings remain)`

## Notes

The deleted production catalog had no runtime consumer: its sole caller was the deleted suite that compared catalog rows with a second command-path classification and asserted descriptive metadata. Live repair behavior remains owned by `active_bucket_repair_session` and the diagnostics/quarantine flows. The exact scan reports 31 unreachable modules, 274 unused symbols, and zero orphaned test modules; the unexpected movement from the prior 272-symbol observation is retained as live shared-worktree drift rather than hidden or baselined.
