---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:5e32547d2d2c091d0b106c23b014cb1fefca70be48b4d500efd1cb6e4dd0fee6'
step_id: 'S91'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---




# Move residual Modelo missing-binding, readiness, export-evidence, amend-wizard, calculate, wizard, and IVA-wallet action selection into application-owned declarations, resolve them through the canonical CLI authority, and delete raw command/result carriers

## Scope

- `src/cadrumo/application/modelo/_export.py`
- `src/cadrumo/application/modelo/_preconditions.py`
- `src/cadrumo/application/modelo/_action_errors.py`
- `src/cadrumo/application/modelo/_iva_wallet_seed.py`
- `src/cadrumo/application/modelo/tests`
- `src/cadrumo/entrypoints/cli/_modelo.py`
- `src/cadrumo/entrypoints/cli/_modelo_behavior_support.py`
- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_export_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_amend_wizard_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_amend_wizard_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_iva_wallet_cli.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_registry_surface.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_100_readiness_missing_bindings.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_amend_wizard_payload.py`

## Description

- Move readiness, amendment-evidence, wizard-retry, and IVA missing-taxpayer decisions into application-owned typed profiles.
- Delete raw export, readiness, amendment, calculate, wizard, and wallet recovery carriers.
- Restrict CLI code to canonical verdict resolution/attachment and retain valid-ID discovery text as factual input guidance.
- Gate the complete declared surface against local action/verdict construction and executable recovery prose.

## Outcome

Commits `c7032818ed`, `916fc9517e`, and `cc7b3926bd` complete the Modelo producer migration; `32d55bd66f` preserves final test formatting. Application declarations own all actions and explicit no-action outcomes, and the CLI contains no duplicated catalogue or schema authority.

Independent verification passes four integration and two direct unit outcome tests; the wider focused selections pass 16 unit plus one IVA integration test. Structural mutations reject local constructors and both command/profile prose classes.

## Notes

- Broader M303 wallet and filing-evidence fixture failures occur before the S91 producers and remain external to this row.
