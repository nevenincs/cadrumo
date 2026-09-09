---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:47e156ba643e759e23156f64639acc87f2b1109d432e071ff17bb3f87e3e6f9c'
step_id: 'S298'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the bare-modelo-string AST census, its production-path allowlist, declaration-module skip, copied source fixtures, and metastate checks; retain Modelo typing at live command and domain boundaries.

## Scope

- `modelo string-usage source census and any stale gate registration`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/core/tests/test_modelo_string_usage.py`
- `M` `src/cadrumo/core/tests/test_clock_seam_usage.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S298.md`
- `verify:` `rg -n "test_modelo_string_usage|bare_modelo_code_offenders" pyproject.toml justfile dev .github src -g "!dev/.logs/**"` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact detector retains the campaign's live red: 31 unreachable modules and 243 unused reachable symbols. Deleting this test-only census did not widen or suppress that production signal.
