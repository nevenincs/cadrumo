---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S141'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S141 Modelo Internal Import Cleanup

Scope: remove residual modelo application-internal reach-through to the `_actions` compatibility facade where focused backend modules already own the implementation.

## Description

- Repointed the public modelo facade to focused action modules for calculation, filing, amendment, external import, verification, and IVA wallet exports.
- Repointed internal modelo helpers away from `_actions.py` and toward focused owners such as `_calculation_actions.py`, `_work_lifecycle.py`, `_action_errors.py`, and `_registry_resources.py`.
- Preserved `_actions.py` as a compatibility facade for legacy private test imports while removing application-internal reach-through.

## Outcome

`rg` found no remaining `_actions` imports inside `src/aeat/application/modelo`. Public package exports continue to resolve through `aeat.application.modelo`.

## Notes

Verification passed for Ruff, compileall, 26 focused history/selector/work-addressing/source-mesh tests, 30 filing-flow tests, 15 export tests, 36 verification-substance tests, and 8 architecture-boundary tests. S142 remains open because the global size-budget gate currently depends on concurrent uncommitted config/budget WIP.
