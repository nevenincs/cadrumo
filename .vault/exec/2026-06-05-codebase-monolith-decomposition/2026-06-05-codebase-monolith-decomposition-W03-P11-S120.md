---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S120'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S120 Modelo Facade And CLI Verification

Scope: verify residual modelo application behavior and public facade imports after action decomposition.

## Description

- Found the public `aeat.application.modelo` facade still importing work-unit lifecycle symbols from `_actions.py` after those functions moved to `_work_lifecycle.py`.
- Updated the facade to import canonical action errors from `_action_errors.py`, work-unit lifecycle CRUD from `_work_lifecycle.py`, workflow actions from `_actions.py`, and `workflow_period_for_work_unit` from `_workflow_gate.py`.
- Preserved the operator-facing CLI contract: entrypoints continue importing the top-level application package, not private application submodules.
- Updated `src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py` to import `create_work_unit` from the public application facade instead of `._actions`.

## Outcome

The modelo application top-level module is again the export facade for consumers. CLI modules and CLI tests no longer reach into private modelo application helper modules for work-unit lifecycle behavior.

## Verification

- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_work_lifecycle.py src/aeat/application/modelo/_registry_resources.py src/aeat/application/modelo/_action_errors.py src/aeat/application/modelo/__init__.py`
- `python -m compileall src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_work_lifecycle.py src/aeat/application/modelo/_registry_resources.py src/aeat/application/modelo/_action_errors.py src/aeat/application/modelo/__init__.py`
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_actions.py src/aeat/application/modelo/tests/test_history.py src/aeat/application/modelo/tests/test_selectors.py src/aeat/application/modelo/tests/test_work_addressing.py -q`
- `uv run --no-sync pytest -m "unit or integration" src/aeat/entrypoints/cli/tests/test_modelo.py src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/tests/test_modelo_work_id_type_hint.py src/aeat/entrypoints/cli/tests/test_modelo_export_verb.py src/aeat/entrypoints/cli/tests/test_modelo_history_verb.py src/aeat/entrypoints/cli/tests/test_modelo_payloads.py -q`
- `uv run --no-sync pytest -m "unit or integration" src/aeat/entrypoints/cli/tests/test_architecture_boundaries.py -q`
- `uv run --no-sync pytest -m "unit or integration" src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py -q`
- `rg -n "from aeat\\.application\\.modelo\\._|import aeat\\.application\\.modelo\\._|from \\.\\..*application\\.modelo\\._" src/aeat/entrypoints src/aeat/adapters src/aeat/domain -g "*.py"`

Result: lint passed, compile passed, 46 focused application tests passed, 134 focused modelo CLI tests passed, 8 architecture-boundary tests passed, 4 profile export roundtrip tests passed, and the private modelo application import scan returned no entrypoint/adapter/domain matches.
