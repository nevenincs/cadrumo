---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S142'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S142 Modelo Facade Verification

Scope: verify residual modelo facade-bound import cleanup preserves application behavior, boundary guards, and `_actions.py` compatibility exports.

## Description

- Verified Ruff and compileall for the modelo application package after the public facade import remapping.
- Verified public `aeat.application.modelo` exports for calculation, amendment, external import, filing, verification, and IVA wallet symbols.
- Verified architecture-boundary tests still reject CLI and adapter reach-through into private application modules.
- Verified focused modelo behavior for action lifecycle, natural work addressing, export, external import, filing, and verification substance.
- Ran the repository hard size-budget gate to record remaining residual offenders.

## Outcome

The modelo facade cleanup preserves behavior and boundary guards. `_actions.py` compatibility remains available while normal consumers resolve through `aeat.application.modelo`.

## Notes

Passing checks: Ruff on touched modelo application modules; compileall for `src/aeat/application/modelo`; public facade smoke import; private-submodule scan across `entrypoints`, `adapters`, and `domain`; 8 architecture-boundary tests; 26 action/work-addressing tests; 15 export tests; 51 import/file-flow tests; and 36 verification-substance tests. The repository size-budget gate still fails on open residual rows for `src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary.py`, `src/aeat/application/overview/tests/test_calendar.py`, and `src/aeat/application/overview/_calendar.py:build_overview_calendar`; it no longer reports modelo production offenders.
