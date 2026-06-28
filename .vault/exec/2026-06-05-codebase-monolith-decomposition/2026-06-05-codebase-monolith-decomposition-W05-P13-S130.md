---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S130'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W05.P13.S130 Final Monolith Inventory

Scope: refresh exact fd, rg, and vaultspec-rag monolith inventory after residual decomposition.

## Description

- Run `fd` inventory for Python files under `src/aeat`.
- Run exact filesystem line-count inventory and list the largest remaining modules.
- Run `rg` checks for budget constants, legacy budget names, and monolith-plan references.
- Run vaultspec-rag semantic search for codebase monolith decomposition size-budget guard surfaces.

## Outcome

The final inventory found 2,215 Python files under `src/aeat`, zero modules over 1250 lines, and zero production callables over 180 lines. The largest remaining modules are at or below the hard budget, led by `src/aeat/adapters/outbound/aeat/sede/_declarations.py` at 1249 lines.

## Notes

`rg` found no remaining legacy budget allowlist names in the active size-guard tests.
