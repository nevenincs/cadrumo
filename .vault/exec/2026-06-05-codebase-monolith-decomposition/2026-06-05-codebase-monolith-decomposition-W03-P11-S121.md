---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S121'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S121 Live IVA Remote-State Extraction

Scope: decompose residual live package root exports into focused private modules behind the public live facade.

## Description

- Extracted IVA compensation history, IVA wallet capture/reconciliation, combined IVA remote-state acquisition, acquisition manifest persistence, redaction helpers, and live-surface timeout helpers into `src/aeat/application/live/_iva_remote_state.py`.
- Kept `src/aeat/application/live/__init__.py` as the public facade for existing `aeat.application.live` consumers.
- Preserved legacy private test compatibility aliases through the package root while sourcing them from focused modules.
- Left expedientes and notifications root functions in place for a later narrower extraction because the current budget was closed by moving the IVA substrate.

## Outcome

`src/aeat/application/live/__init__.py` is reduced from 1339 lines to 338 lines. The new IVA remote-state module is 1018 lines and remains below the current hard module budget.

## Notes

No schema or CLI behavior changed; this was a mechanical application-layer extraction.
