---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S154'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S154 Non-CLI Callable Split

Scope: decompose remaining oversized non-CLI production callables behind existing backend facades.

## Description

- Split Google Sheets apply orchestration into focused spreadsheet, locale, tab/grid, value-write, and structural-request helpers.
- Split ledger merge persistence and event construction helpers out of the merge transaction callable.
- Split run-context replay marker resolution while preserving fail-closed run-id validation before filesystem access.
- Split registry revision-section validation into surface and closure helper passes while preserving the public validation entry point.
- Split IVA compensation reconciliation decision branches around a shared reconciliation context.
- Split Cl@ve Movil fresh-login session construction into a focused helper to keep the locked login path under callable budget.
- Repaired the observability replay canonicity source scan after the tests package move.

## Outcome

The targeted non-CLI production callables are decomposed behind their existing module facades, and the hard callable/module budget guard passes for the focused slice.

## Notes

Verification passed for Ruff, compileall, 30 Google Sheets apply tests, 18 ledger split/merge tests, 31 observability context/replay/logging tests, 19 IVA wallet reconciliation tests, 136 registry schema/referential-integrity tests, 51 Cl@ve/auth smoke tests, and the 2-test hard codebase size-budget guard. The observability gate caught and fixed a validation-order regression before commit.
