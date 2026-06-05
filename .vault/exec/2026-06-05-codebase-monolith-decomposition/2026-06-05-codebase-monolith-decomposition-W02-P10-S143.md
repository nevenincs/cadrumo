---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S143'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S143 Config Custody Registrar Split

## Scope

Split the residual oversized config custody command registrar into focused transport helpers.

## Description

- Extracted unlock, lock, rekey, recover, show-recovery, and verify-recovery command registration into separate helpers.
- Kept command bodies as CLI transport: activate output language, delegate to application services, emit typed payloads, and translate boundary errors.
- Left custody policy in backend services.

## Outcome

`register_custody_commands` is now a small composition function and no longer exceeds the callable budget.

## Notes

No command behavior or option shape was changed.
