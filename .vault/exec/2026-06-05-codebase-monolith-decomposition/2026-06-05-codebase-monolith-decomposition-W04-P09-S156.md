---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S156'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S156 Auth Production Split

Scope: decompose the oversized AEAT auth production modules behind existing auth facades.

## Description

- Moved authenticator boundary records and browser protocols into `_authenticator_types.py`.
- Moved Cl@ve Movil pure support records, policy construction, diagnostics helpers, and failure classes into `_clave_movil_support.py`.
- Moved Cl@ve Movil page-driving methods into `_clave_movil_page_flow.py`.
- Preserved compatibility imports from `_authenticator.py` and `_clave_movil.py`.
- Updated the error registry qualname for `_PersistedSessionInvalidError` after its module move.
- Split the oversized auth authenticator test module into `_authenticator_support.py` and `test_authenticator_part1.py`.

## Outcome

The auth production and auth test surfaces are below the hard size budget while keeping public auth imports and existing private test imports working.

## Notes

Verification passed for Ruff, compileall, 80 focused auth tests, and the 2-test hard size-budget guard. The broader S156 row remains open for `_declarations.py`, core config, and record-design production surfaces.
