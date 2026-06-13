---
tags: ['#exec', '#live-iva-compensation-wallet']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S102'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-05-clave-session-reuse-diagnostics-reference]]'
---


# W10.P24.S102 auth diagnostic show contract repair

Scope: Wave W10, Phase P24, Step S102.

## Description

- Repair the encrypted Cl@ve auth diagnostic `show` CLI so S101 phone-state triage can inspect a failed auth attempt.
- Keep diagnostic output redacted and avoid copying private HTML or taxpayer values into the vault.

## Outcome

`aeat config auth diagnostics show` crashed with `AttributeError` because the CLI rendered `operator_report_commands` while `AuthDiagnosticDetail` did not carry that field. The application detail model now supplies the report command choices, and the existing encrypted diagnostic test asserts the command list.

Validation passed:

- `uv run --no-sync pytest src/aeat/application/auth/test_diagnostics.py::test_auth_diagnostics_list_and_show_redact_page_bodies -q`
- `uv run --no-sync ruff check src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_diagnostics.py`
- `uv run --no-sync aeat config auth diagnostics show 20260605T084306Z` returned redacted detail and operator-report commands.

No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## Notes

The live diagnostic body stayed redacted. This record includes only the command shape and outcome, not private HTML, screenshot contents, tax amounts, or raw identity values.
