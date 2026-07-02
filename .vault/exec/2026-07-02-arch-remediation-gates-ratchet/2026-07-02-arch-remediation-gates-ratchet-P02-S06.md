---
tags:
  - '#exec'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S06'
related:
  - '[[2026-07-02-arch-remediation-gates-ratchet-plan]]'
---

# Enumerate application adapter import pins

## Scope

- `.importlinter`

## Description

- Grounded discovery with `vaultspec-rag search` using production-focused noise filters, then confirmed the concrete imports with AST-based filesystem enumeration at `HEAD`.
- Ignored `TYPE_CHECKING` imports and included local runtime imports so the gate reflects executable coupling.
- Compared committed `HEAD` and working-tree enumeration before writing pins.

## Outcome

The production application source-module baseline is 77 module-level pins to `aeat.adapters.**`.

## Notes

The working tree and committed `HEAD` produced the same 77-module set.
