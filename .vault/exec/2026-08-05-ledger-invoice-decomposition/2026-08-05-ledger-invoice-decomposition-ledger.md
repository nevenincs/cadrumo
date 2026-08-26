---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:df46a151786eff55a02ec456048d14ea9e7b1498fa3025478ff24fdf631f73be'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# `ledger-invoice-decomposition` ledger

## Changes

- `S01` `T` `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`
- `S02` `T` `src/cadrumo/domain/calculations/registry/_ledger_impatriado_bindings.py`
- `S03` `T` `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`
- `S04` `T` `src/cadrumo/application/aggregation/_renta_income_ledger.py`
- `S05` `T` `src/cadrumo/application/modelo/_calculation_actions.py`
- `S06` `T` `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`
- `S07` `T` `src/cadrumo/domain/iva/_schema.py`
- `S08` `T` `src/cadrumo/domain/iva/tests`
- `S09` `T` `src/cadrumo/_data/registry/aeat/legal`
- `S10` `T` `src/cadrumo/_data/registry/aeat/legal`
- `S11` `T` `src/cadrumo/application/aggregation/_renta_income_ledger.py`
- `S12` `T` `src/cadrumo/domain/transactions`
- `S13` `T` `src/cadrumo/domain/transactions`
- `S14` `T` `src/cadrumo/application/modelo`
- `S15` `T` `src/cadrumo/domain/calculations/registry/tests`
- `S16` `T` `src/cadrumo/domain/calculations/registry/tests`
- `S17` `T` `src/cadrumo/application/calculations/tests`
- `S18` `T` `src/cadrumo/domain/iva/_components.py`
- `S19` `T` `src/cadrumo/domain/invoices/_models.py`
- `S20` `T` `src/cadrumo/application/aggregation`
- `S21` `T` `src/cadrumo/_data/corpus/normatives/html`
- `S22` `T` `src/cadrumo/application/aggregation/tests`
- `S23` `T` `src/cadrumo/application/aggregation/tests`
- `S24` `T` `src/cadrumo/application/aggregation/tests`
- `S25` `T` `src/cadrumo/tests`
- `S26` `T` `src/cadrumo/application/aggregation/_modelo_bindings.py`
- `S27` `T` `src/cadrumo/_data/registry/aeat/legal`
- `S28` `T` `src/cadrumo/application/aggregation/tests/test_invoice_retencion_routing.py`
- `S29` `T` `src/cadrumo/application/aggregation/tests/test_cross_domain_invoice_scenario.py`
- `S30` `T` `src/cadrumo/application/aggregation/tests/test_cross_domain_invoice_scenario.py`
- `S31` `T` `src/cadrumo/domain/calculations/registry/tests`
- `S32` `T` `src/cadrumo/domain/calculations/registry/tests`
- `S33` `T` `src/cadrumo/domain/calculations/registry/tests`
- `S34` `T` `src/cadrumo/_data/corpus/normatives/html`
- `S35` `T` `src/cadrumo/domain/iva/tests/test_component_expectations.py`
- `S36` `T` `.vault/adr`
- `S37` `T` `src/cadrumo/domain/invoices/_models.py`
- `S37` `T` `src/cadrumo/domain/invoices/_decomposition.py`
- `S38` `T` `src/cadrumo/application/aggregation/_renta_income_ledger.py`
- `S39` `T` `src/cadrumo/domain/transactions/_models.py`
- `S39` `T` `src/cadrumo/domain/transactions/_dates.py`
- `S39` `T` `src/cadrumo/application/aggregation/_iva_ledger.py`
- `S40` `T` `src/cadrumo/_data/corpus/normatives/html`
- `S41` `T` `src/cadrumo/domain/invoices/_models.py`
- `S42` `T` `src/cadrumo/domain/invoices/_models.py`
- `S42` `T` `src/cadrumo/domain/invoices/_decomposition.py`
- `S43` `T` `src/cadrumo/domain/invoices/_models.py`
- `S44` `T` `src/cadrumo/domain/invoices/_models.py`
- `S44` `T` `src/cadrumo/domain/invoices/_validators.py`
- `S45` `T` `src/cadrumo/domain/invoices/_models.py`
- `S45` `T` `src/cadrumo/application/aggregation`
- `S46` `T` `src/cadrumo/application/aggregation`
- `S46` `T` `src/cadrumo/application/invoices`
- `S47` `T` `src/cadrumo/application/aggregation/_invoice_retencion.py`
- `S47` `T` `src/cadrumo/application/invoices`
- `S48` `T` `src/cadrumo/application/aggregation`
- `S49` `T` `src/cadrumo/application/aggregation/tests`
- `S50` `T` `src/cadrumo/domain/invoices/tests`
- `S51` `T` `src/cadrumo/_data/corpus/normatives/html`
- `S51` `T` `src/cadrumo/domain/invoices/_models.py`
- `S51` `T` `src/cadrumo/domain/invoices/tests`
- `S52` `T` `src/cadrumo/domain/transactions/_models.py`
- `S52` `T` `src/cadrumo/domain/transactions/tests/test_gross_invariant.py`
- `S53` `T` `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`
- `S53` `T` `src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py`
- `S53` `T` `src/cadrumo/entrypoints/cli/tests/test_m349_business_invoice_export.py`
- `S53` `T` `src/cadrumo/entrypoints/cli/tests/test_ledger_validation_paths.py`
- `S55` `T` `src/cadrumo/application/invoices`
- `S55` `T` `src/cadrumo/entrypoints/cli`
- `S56` `T` `src/cadrumo/domain/renta/_ledger_expenses.py`
- `S56` `T` `src/cadrumo/domain/renta/tests/test_ledger_expenses.py`
- `S57` `T` `src/cadrumo/application/aggregation/_renta_ledger.py`
- `S57` `T` `src/cadrumo/application/aggregation/tests/test_renta_ledger.py`
- `S57` `T` `src/cadrumo/domain/renta/_ledger_expenses.py`
- `S58` `T` `src/cadrumo/application/aggregation/_renta_gasto_ledger.py`
- `S58` `T` `src/cadrumo/application/aggregation/tests/test_renta_gasto_aggregation.py`
- `S60` `T` `src/cadrumo/_data/registry/aeat/categories/profiles/2024.toml`
- `S60` `T` `src/cadrumo/_data/registry/aeat/categories/profiles/2025.toml`
- `S60` `T` `src/cadrumo/domain/categories/_spending_category.py`
- `S61` `T` `src/cadrumo/_data/registry/aeat/categories/profiles/2024.toml`
- `S61` `T` `src/cadrumo/_data/registry/aeat/categories/profiles/2025.toml`
- `S61` `T` `src/cadrumo/domain/categories/_spending_category.py`
