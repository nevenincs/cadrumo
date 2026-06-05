---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S143'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S143 Custody Registrar Split

Scope: `src/aeat/entrypoints/cli/_config/_custody.py`; `src/aeat/entrypoints/cli/_config/tests`.

## Description

- Split the residual config custody registrar into focused root-command registration helpers.
- Preserve root `config unlock`, `lock`, `rekey`, `recover`, `show-recovery`, and `verify-recovery` transport semantics.

## Outcome

- `register_custody_commands` is now a thin registrar that delegates to per-command helpers.
- Verified by `ruff check` on the touched config files and by config lifecycle tests.

## Notes

- No policy moved into CLI; the command helpers continue to call application services.
