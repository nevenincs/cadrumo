---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S08'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P04.S08 Codebase Size Guard Expansion

Scope: `src/aeat/tests`, `src/aeat/entrypoints/cli/tests`.

## Description

- Use RAG and exact inventory to locate the existing codebase-wide size guard.
- Extend `test_codebase_size_budgets.py` so module budgets cover all tracked Python modules, including oversized tests and support fixtures.
- Add the required `hex_core` marker for collection compatibility.
- Resolve the guard's `git ls-files` executable path explicitly and document the fixed-argv subprocess rationale.

## Outcome

The codebase-wide guard now freezes the current oversized tracked Python module inventory and callable line budgets. Focused guard tests and ruff passed.

## Notes

The guard remains a ratchet with explicit legacy budgets; final hard 1250-line enforcement is still tracked by later plan rows after the remaining backend/core decomposition waves complete.
