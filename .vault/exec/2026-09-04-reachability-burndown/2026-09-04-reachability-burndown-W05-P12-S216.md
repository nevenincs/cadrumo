---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:8a0b97f7b0773907c7fc49dd4e5d63e34861a5905770a0ac8a3049cb50ec1257'
step_id: 'S216'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-only CALCULATION_ROUTE_ID alias, then follow the exposed reachability edge through the wholly unreachable core route enum and test-only operator-surface calculation-workflow catalogue; remove both abandoned modules, their synthetic/identity-census tests, and stale package documentation while retaining the live staged resolver ownership and real CLI calculation paths.

## Scope

- `Modelo calculation-route owner`
- `abandoned core/operator workflow identity slice and tests`
- `operator-surface package documentation`
- `focused resolver tests`
- `exact reachability signal`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/application/modelo/calculation_route.py`
- `M` `src/cadrumo/application/modelo/tests/test_calculation_route.py`
- `M` `src/cadrumo/application/operator_surface/__init__.py`
- `D` `src/cadrumo/core/calculation_route.py`
- `D` `src/cadrumo/application/operator_surface/calculation_workflows.py`
- `D` `src/cadrumo/application/operator_surface/tests/test_calculation_workflows.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S216.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_calculation_route.py dev/quality/tests/test_no_test_only_public_alias.py` -> `pass (32 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/calculation_route.py src/cadrumo/application/modelo/tests/test_calculation_route.py src/cadrumo/application/operator_surface/__init__.py dev/quality/tests/test_no_test_only_public_alias.py` -> `pass`
- `verify:` `rg -n "CALCULATION_ROUTE_ID|ModeloCalculationRouteId|SupportedModeloCalculationWorkflow|calculation_workflows" src dev --glob '*.py'` -> `pass (no matches)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 62 unreachable modules, 310 exact unused symbols, 15 orphaned tests, 2027/2090 shipped modules reachable)`
