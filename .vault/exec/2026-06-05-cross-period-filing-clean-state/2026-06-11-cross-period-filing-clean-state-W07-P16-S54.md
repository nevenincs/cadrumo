---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-11'
step_id: 'S54'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
---

# `cross-period-filing-clean-state` `W07.P16.S54` exec - operator inventory tests

## Description

Cover the new operator dependency inventory and blocker output in the real CLI UX test surface.

## Outcome

`test_work_dependencies_lists_cross_period_inventory` proves Modelo 390 year filtering returns registry-derived `303` upstream dependencies. `test_work_dependencies_surfaces_current_clean_state_blockers` proves a target read for `390/2025/0A` reports unclean active-bucket state and names missing upstream filing/observation blockers.

## Verification

Command passed: `uv run pytest src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py -m integration -q` with 20 tests passing.

Command passed: `uv run pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_verificado_completo_regression.py -q` with 88 tests passing.

Command passed: `uv run ruff check` on the touched CLI, payload, application, deadline, and registry surfaces.
