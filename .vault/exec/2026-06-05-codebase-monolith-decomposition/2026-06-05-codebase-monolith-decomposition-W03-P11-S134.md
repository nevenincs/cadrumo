---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S134'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S134 Modelo Calculation Extraction Verification

Scope: verify residual modelo calculation extraction preserves behavior and public facade imports.

## Description

- Verified calculation workflow imports through `aeat.application.modelo` remain available after extraction into `_calculation_actions.py` and `_calculation_helpers.py`.
- Verified the natural-key CLI calculation lane still resolves visible filing targets without requiring operators to copy raw work-unit or calculation-revision IDs.
- Verified CLI/adapters/domain do not import private modelo application submodules.
- Confirmed source-owned bucket aggregation inputs are rejected before calculation persistence and before operator overrides can mask bucket-derived substrate.

## Outcome

Calculation extraction preserves the public application facade and the operator-facing natural-key CLI behavior. Raw internal IDs remain compatibility/escape-hatch surfaces, not the normal calculation path.

## Verification

- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_calculation_actions.py src/aeat/application/modelo/_calculation_helpers.py src/aeat/application/modelo/_registry_helpers.py src/aeat/application/modelo/__init__.py`
- `python -m compileall src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_calculation_actions.py src/aeat/application/modelo/_calculation_helpers.py src/aeat/application/modelo/_registry_helpers.py src/aeat/application/modelo/__init__.py`
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_actions.py src/aeat/application/modelo/tests/test_source_mesh_calculation.py src/aeat/application/modelo/tests/test_work_addressing.py -q`
- `uv run --no-sync pytest -m "unit or integration" src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py src/aeat/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py src/aeat/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py -q`
- `rg -n "from aeat\\.application\\.modelo\\._|import aeat\\.application\\.modelo\\._|from \\.\\..*application\\.modelo\\._" src/aeat/entrypoints src/aeat/adapters src/aeat/domain -g "*.py"`

Result: lint passed, compile passed, 30 calculation-focused application tests passed, 29 calculation/natural-key CLI tests passed, and the private modelo application import scan returned no entrypoint/adapter/domain matches.
