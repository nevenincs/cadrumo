---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:39a9b86ab811fad8cb8e495883f5d0dea515543c98e1db3d5b88434e5e384d2e'
step_id: 'S217'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the non-material reflective source-resolver enrollment test module instead of repairing its hand-maintained package census, qualified-name classifications, and pinned discovery counts; retain the production calculation-route validator for executable membership, unique resolver/source ownership and stage identity, with exact reachability as the dormant-resolver detector.

## Scope

- `Source-resolver enrollment census tests`
- `live calculation-route invariant tests`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `D` `src/cadrumo/application/aggregation/tests/test_source_resolver_enrollment.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S217.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_calculation_route.py dev/quality/tests/test_no_test_only_public_alias.py` -> `pass (32 passed)`
- `verify:` `uv run --no-sync python -m py_compile src/cadrumo/application/export/google_operation.py` -> `pass (peer-owned parse blocker cleared)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 62 unreachable modules, 311 exact unused symbols, 16 orphaned tests, 2028/2091 shipped modules reachable; concurrent graph drift classified separately)`
