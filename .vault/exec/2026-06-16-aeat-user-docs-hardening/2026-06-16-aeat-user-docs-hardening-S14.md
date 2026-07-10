---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S14'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden import-bank-statements.md

## Scope

- `docs/how-to/import-bank-statements.md`

## Description

- Verify-close: read `import-bank-statements.md` in full against the hardening standard and confirm its audit findings are resolved at HEAD.
- Confirm finding M4 (no sample CSV / column format): the page now shows the concrete bank-CSV format (semicolon separator, comma decimals, `Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda` header with worked rows) and documents the sign-carries-direction convention.
- Confirm the dry-run-first workflow, the recognized provider list, and the manual-add path are documented with resolving commands.

## Outcome

- Page verified compliant at HEAD; audit finding M4 resolved (2026-06-19 batch). Delta: none required this pass.
- Imperative steps, precondition block, dry-run-first safety, format example, resolving cross-links.

## Notes

- Residual m1 (missing-file import traceback) is an APP-side finding, already fixed per the audit (clean typed refusal). CLI conformance gate green.
