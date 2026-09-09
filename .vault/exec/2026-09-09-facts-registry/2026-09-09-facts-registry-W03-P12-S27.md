---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:6e01e6654bcbaa03b9dce52c4b44a387748eb11aae1dd0694b213bfeec9fd908'
step_id: 'S27'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---


# Rewire invoice slot percentage interpretation

## Scope

- `src/cadrumo/domain/invoices/enums.py`

## Changes


- `M` `src/cadrumo/domain/invoices/enums.py`
- `M` `src/cadrumo/domain/invoices/models.py`
- `M` `src/cadrumo/domain/invoices/tests/test_models.py`
- `M` `src/cadrumo/domain/invoices/tests/test_rate_parity.py`
- `M` `src/cadrumo/domain/invoices/tests/test_retencion_consistency.py`
- `M` `src/cadrumo/domain/invoices/tests/test_retencion_persistence_invariant.py`
- `M` `src/cadrumo/application/invoices/catalogue_creation.py`
- `M` `src/cadrumo/application/invoices/creation_wizard.py`
- `M` `src/cadrumo/application/invoices/tests/test_wizard_field_grammar.py`
- `M` `src/cadrumo/application/ledger/confirmed_field_resolution.py`
- `M` `src/cadrumo/application/ledger/invoice_confirmation.py`
- `M` `src/cadrumo/application/ledger/tests/test_evidence_draft_rate_slot.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings_invoice_iva.py`
- `M` `src/cadrumo/application/aggregation/tests/test_income_sales_invoice_evidence.py`
- `M` `src/cadrumo/application/aggregation/tests/test_invoice_retencion_routing.py`
- `M` `src/cadrumo/application/aggregation/tests/test_invoice_retencion_store_roundtrip.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_invoice_retencion_aggregate_cli.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W03-P12-S27.md`
- `verify:` `uv run pytest src/cadrumo/domain/invoices/tests/test_models.py src/cadrumo/domain/invoices/tests/test_rate_parity.py src/cadrumo/application/invoices/tests/test_wizard_field_grammar.py -q` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/invoices/enums.py src/cadrumo/domain/invoices/models.py src/cadrumo/application/invoices/catalogue_creation.py src/cadrumo/application/invoices/creation_wizard.py src/cadrumo/application/ledger/confirmed_field_resolution.py src/cadrumo/application/ledger/invoice_confirmation.py src/cadrumo/application/aggregation/_modelo_bindings_invoice_iva.py src/cadrumo/domain/iva/invoice_classification.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/invoices/enums.py src/cadrumo/domain/invoices/models.py src/cadrumo/domain/invoices/tests/test_models.py src/cadrumo/domain/invoices/tests/test_rate_parity.py src/cadrumo/application/invoices/catalogue_creation.py src/cadrumo/application/invoices/creation_wizard.py src/cadrumo/application/invoices/tests/test_wizard_field_grammar.py src/cadrumo/application/ledger/confirmed_field_resolution.py src/cadrumo/application/ledger/invoice_confirmation.py src/cadrumo/application/ledger/tests/test_evidence_draft_rate_slot.py src/cadrumo/application/aggregation/_modelo_bindings_invoice_iva.py` -> `pass`
