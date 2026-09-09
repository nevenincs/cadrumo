---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:e3e00e46707e1cfd263c71ecf043247e8b7287e8ebbb7d4d6505feb1480cf2e5'
step_id: 'S303'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the paid-down type-ignore enrollment roster, subtraction logic, historical paydown prose, and stale-entry test; enforce the zero-state rationale rule directly without a baseline.

## Scope

- `type-ignore rationale gate`
- `focused gate`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/tests/test_type_ignore_rationale_inventory.py`
- `M` `src/cadrumo/application/modelo/projection.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S303.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_type_ignore_rationale_inventory.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The simplified zero-state gate exposed one live suppression in `_comparison_year_pair`; destructuring the already length-checked sorted list removed that suppression instead of enrolling or annotating it. The exact production detector remains red on the wider campaign findings.
