---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:8fab8681025d7aa4ea15f0a6823f4be6038efdd3dd8fbd615db43ce7e00f3bf1'
step_id: 'S22'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
## Scope

- Promote the canonical calculation binding-channel resolver through the application Modelo facade.
- Prove the public binding is the exact existing owner object.

## Description

- Import `resolve_calculation_binding_channels` directly from `_calculation_resolution` in the application facade.
- Add the function to the facade `__all__` without a wrapper, alias, bridge, or compatibility layer.
- Add a direct runtime identity regression while retaining the existing replay behavior proof.
- Run focused tests, Ruff, strict BasedPyright, sole-definition searches, runtime identity, diff hygiene, and formal review.

## Outcome

- `cadrumo.application.modelo.resolve_calculation_binding_channels` is now the exact function declared by `_calculation_resolution.py`.
- The implementation still has exactly one declaration and no duplicate body or forwarding wrapper.
- The focused owner test module passed 2 tests.
- Ruff and strict BasedPyright passed with zero diagnostics; runtime identity and scoped diff checks passed.
- Formal review returned PASS with no findings.

## Notes

- Fresh Vault RAG grounded the accepted read-model ADR. During independent review the code RAG service timed out twice under load; the reviewer completed exact scoped source and identity inspection and recorded that boundary.
- No fake, stub, patch, skip, alias, compatibility surface, or mirrored business logic was introduced.
