---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6407a4ee297971ae36a1583dfec2f888c4b2b757596341815ab1dfb95d777b0b'
step_id: 'S03'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Declare locus and shape on all 55 Path-typed parameters

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_registry_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_review_package_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_live_foundation_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_live_iva_wallet_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_operations_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_evidence_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_classification_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_inventory_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_invoice_intake_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_audit_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_calculations_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_filing_record_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_reconcile_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_work_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_app_quickfile_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_auth_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_profile_command_specs.py`
- `verify:` `COMMAND_GRAPH rebuild + ruff check` -> `pass`
