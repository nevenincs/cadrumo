---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S119'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S119 Modelo Action Decomposition

Scope: decompose residual modelo application actions by natural-key work and revision workflow behind the modelo facade.

## Description

- Extracted registry resource lookup helpers from `src/aeat/application/modelo/_actions.py` into `src/aeat/application/modelo/_registry_resources.py`.
- Extracted registry validation and revision-integrity helpers from `src/aeat/application/modelo/_actions.py` into `src/aeat/application/modelo/_registry_helpers.py`.
- Extracted work-unit lifecycle actions from `src/aeat/application/modelo/_actions.py` into `src/aeat/application/modelo/_work_lifecycle.py`.
- Kept `src/aeat/application/modelo/_actions.py` as the application workflow orchestrator for calculation, verification, filing, amendment, and import flows.
- Preserved package-level consumer behavior by importing the extracted functions back into `_actions.py`; consumers continue to use the public modelo facade rather than private helper modules.
- Removed duplicated action error declarations from `_actions.py`; canonical action errors live in `src/aeat/application/modelo/_action_errors.py`.
- Collapsed duplicated registry resource helpers so `_registry_helpers.py` delegates registry authority and root lookup to `_registry_resources.py`.
- Added follow-up rows `W03.P11.S133` through `W03.P11.S140` because `_actions.py` remains above the hard module budget after this first residual split.

## Outcome

The residual modelo action surface now separates registry resources, registry helper logic, action errors, and work-unit lifecycle CRUD from calculation/revision workflow orchestration while preserving the public application import surface. `_actions.py` is reduced to 2889 lines in this slice; it remains a residual monolith and the plan now carries follow-up extraction rows through the final 1250-line budget closure.

## Verification

- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_work_lifecycle.py src/aeat/application/modelo/_registry_resources.py src/aeat/application/modelo/_registry_helpers.py src/aeat/application/modelo/_action_errors.py src/aeat/application/modelo/__init__.py`
- `uv run --no-sync python -m compileall src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_work_lifecycle.py src/aeat/application/modelo/_registry_resources.py src/aeat/application/modelo/_registry_helpers.py src/aeat/application/modelo/_action_errors.py`
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_actions.py src/aeat/application/modelo/tests/test_history.py src/aeat/application/modelo/tests/test_selectors.py src/aeat/application/modelo/tests/test_work_addressing.py -q`

Result: lint passed, compile passed, and 46 focused application tests passed.
