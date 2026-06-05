---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S141'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S141 Modelo Internal Facade Cleanup

## Scope

Remove residual modelo application-internal imports from the `_actions` compatibility facade where focused backend modules already own the implementation.

## Description

- Redirect `WorkUnitNotFoundError` imports to `_action_errors`.
- Redirect work lifecycle imports to `_work_lifecycle`.
- Redirect calculation revision imports to `_calculation_actions`.
- Redirect IVA wallet and clean-state helpers to their owning backend modules.
- Preserve `_actions` as a compatibility export facade for package consumers and existing tests.

## Outcome

Modelo sibling services now call owning backend modules directly instead of using `_actions` as an internal dependency hub.

## Notes

The public package facade and `_actions` compatibility exports remain intentionally available.
