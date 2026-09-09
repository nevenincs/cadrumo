---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:89a374b8dc5d70f3d2cf119a3d93e7fe83f6224384448674733fc29bec3e7d2b'
step_id: 'S215'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the wholly unused MODELO_WORK_VERIFY_PROGRESS_UNIT constant and export from Modelo operation definitions after proving verification progress is owned by the typed work-review denominator and the operation definition carries no progress-unit field.

## Scope

- `Modelo operation definitions and focused verification/registration tests`
- `exact reachability signal`
- `focused gates`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S215.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/tui/modelo/tests/test_c4_verify_action.py` -> `pass (10 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/operation_definitions.py src/cadrumo/application/modelo/tests/test_lifecycle_operation_conformance.py src/cadrumo/entrypoints/tui/modelo/tests/test_c4_verify_action.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `rg -n "MODELO_WORK_VERIFY_PROGRESS_UNIT" src dev --glob '*.py'` -> `pass (no matches)`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_lifecycle_operation_conformance.py src/cadrumo/entrypoints/tui/modelo/tests/test_c4_verify_action.py` -> `fail (2 unrelated existing writer-census failures: file and verify)`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/tui/modelo/tests/test_c4_verify_action.py src/cadrumo/application/modelo/tests/test_file_flow_verify.py` -> `fail (1 unrelated existing parent-coordinate fixture failure; 23 passed)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 63 unreachable modules, 311 exact unused symbols, 15 orphaned tests, 2028/2092 shipped modules reachable)`
