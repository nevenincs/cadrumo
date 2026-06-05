---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S144'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S144 Profile Censo Registrar Split

## Scope

Split the residual oversized profile censo registrar into focused transport helpers.

## Description

- Extracted refresh, show, compare, and apply command registration into separate helpers.
- Preserved `CensoSyncService` as the backend owner for censo behavior.
- Kept the top-level `register` function as a Typer subgroup composition facade.

## Outcome

The censo registrar no longer exceeds its callable budget and remains a CLI consumer of backend services.

## Notes

No command behavior or option shape was changed.
