---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S133'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S133 Modelo Calculation Extraction

Scope: extract residual modelo calculation and bucket-aggregation workflows behind the modelo application facade without moving policy to CLI.

## Description

- Extracted `calculate_modelo_revision`, `calculate_modelo_revision_from_bucket_aggregation`, `get_calculation_revision`, `list_calculation_revisions`, and `mark_revision_verificado_completo` into `src/aeat/application/modelo/_calculation_actions.py`.
- Extracted shared calculation observation, work-unit loading, and registry snapshot helpers into `src/aeat/application/modelo/_calculation_helpers.py`.
- Kept `src/aeat/application/modelo/_actions.py` as the compatibility facade for private callers while the public `aeat.application.modelo` facade remains unchanged.
- Preserved IVA wallet, ledger preflight, binding resolution, bucket event, and revision persistence behavior inside the application layer.
- Reduced `src/aeat/application/modelo/_actions.py` from 2889 lines after S119 to 2107 lines.

## Outcome

Calculation and bucket-aggregation workflows now live in focused application modules behind the existing modelo facades. `_actions.py` remains above the final 1250-line budget, so the remaining open rows continue with verification, filing, amendment, and import extraction.

## Verification

- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_calculation_actions.py src/aeat/application/modelo/_calculation_helpers.py src/aeat/application/modelo/__init__.py`
- `uv run --no-sync python -m compileall src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_calculation_actions.py src/aeat/application/modelo/_calculation_helpers.py`
- `uv run --no-sync pytest -q --tb=short src/aeat/application/modelo/tests/test_actions.py src/aeat/application/modelo/tests/test_history.py src/aeat/application/modelo/tests/test_selectors.py src/aeat/application/modelo/tests/test_work_addressing.py`
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_source_mesh_calculation.py -q`
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_actions.py src/aeat/application/modelo/tests/test_source_mesh_calculation.py src/aeat/application/modelo/tests/test_work_addressing.py -q`

Result: lint passed, compile passed, 46 focused modelo application tests passed, 4 source-mesh calculation tests passed, and the combined 30-test calculation application lane passed.
