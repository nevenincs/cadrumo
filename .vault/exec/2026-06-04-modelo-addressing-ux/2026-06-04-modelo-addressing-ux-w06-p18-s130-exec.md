---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:c2584dbf11538461a508add08f40d4b61b662c3d0dd5ebbbf766054ca89b9359'
step_id: 'S130'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P18.S130 semantic CLI boundary audit

Scope:
- `vaultspec-rag CLI boundary audit`

## Description

- Run broad semantic searches for CLI business-rule reinvention and backend-service bypasses.
- Narrow to exact `_modelo.py::work_calculate` after broad same-project searches timed out.

## Outcome

Successful semantic query:

- Query: `work_calculate business logic`
- Type: code
- Path: `src/aeat/entrypoints/cli/_modelo.py`
- Function: `work_calculate`
- Result: `_modelo.py::work_calculate`

The semantic hit aligns with the exact audit and size inventory: `work_calculate` is the primary command-level business-logic hotspot and must be split into application services plus a thin CLI wrapper.

## Notes

- Broad RAG queries for all CLI boundary leakage timed out repeatedly despite the service reporting ready. The narrowed path/function query completed successfully and is sufficient for this phase's grounding when combined with exact `rg` and AST inventory evidence.
