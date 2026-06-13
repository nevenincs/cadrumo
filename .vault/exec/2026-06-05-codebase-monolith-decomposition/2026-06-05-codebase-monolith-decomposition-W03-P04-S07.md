---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S07'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P04.S07 Backend ADR Queue

Scope: `.vault/adr`, `src/aeat/application`, `src/aeat/domain`, `src/aeat/adapters`, `src/aeat/core`.

## Description

- Refresh exact over-1250-line inventory for `src/aeat`.
- Run resident RAG semantic search for hexagonal boundary and facade context.
- Add research evidence for remaining backend decomposition boundaries.
- Add an accepted ADR preserving hexagonal ownership and top-level public facades during decomposition.
- Extend the plan with explicit residual CLI, application, domain, adapter, persistence, core, and final static-guard rows.

## Outcome

Backend decomposition is now queued explicitly instead of being hidden behind a single vague row. The plan references ADR and research evidence, and the remaining work is split by architecture boundary and verification lane.

## Notes

The final static guard is not closed. Current inventory still contains modules over 1250 lines, so S08 remains open until the hard guard is true.
