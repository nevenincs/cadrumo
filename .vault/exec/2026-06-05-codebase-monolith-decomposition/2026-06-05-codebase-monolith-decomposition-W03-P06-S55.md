---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S55'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S55 Ledger Actions Facade Decomposition

Scope: `W03.P06.S55` decomposes application ledger actions by orchestration boundary behind the public ledger application facade.

## Description

- Confirm `src/aeat/application/ledger/_actions.py` is now a compatibility export facade.
- Confirm action ownership is split across focused modules for common helpers, classification, export, import, lifecycle, manual mutation, and split/merge workflows.
- Confirm `src/aeat/application/ledger/__init__.py` remains the top-level consumer facade for application callers.
- Run lint over the decomposed ledger action modules.

## Outcome

The ledger action monolith has been decomposed in the worktree. The compatibility `_actions.py` module is 58 lines, and the largest extracted action module remains below the 1250-line target. Ruff reported no findings for the ledger action facade and extracted modules.

## Notes

No CLI business logic was added. Private imports between focused ledger action modules remain package-internal implementation detail; external consumers continue to import from `aeat.application.ledger`.
