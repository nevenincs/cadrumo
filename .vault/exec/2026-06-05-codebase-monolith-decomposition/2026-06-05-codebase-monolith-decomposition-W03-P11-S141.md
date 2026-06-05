---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S141'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S141 Modelo Facade Reach-Through Cleanup

Scope: remove residual modelo application-internal reach-through to `_actions.py` where focused backend modules own the implementation.

## Description

- Rechecked semantic and direct discovery for modelo work-unit, revision, export, projection, and calculation flows before changing imports.
- Confirmed `_calculate_input.py`, `_export.py`, `_projection.py`, `_work_addressing.py`, and filing helpers already import focused backend modules rather than the `_actions.py` compatibility facade.
- Changed the public `aeat.application.modelo` facade to re-export calculation, amendment, import, filing, verification, and IVA wallet symbols from their focused backend modules instead of the `_actions.py` compatibility bundle.
- Kept `_actions.py` available for legacy compatibility exports and application-private tests that intentionally exercise compatibility aliases or private helpers.

## Outcome

The public package initializer is now the consumer-facing facade while `_actions.py` remains a legacy compatibility facade. Production entrypoints, adapters, and domain modules do not reach into private modelo application modules.

## Notes

Ruff, compileall, public facade smoke imports, architecture-boundary tests, and private-submodule consumer scans passed after the cleanup. No CLI business logic was added.
