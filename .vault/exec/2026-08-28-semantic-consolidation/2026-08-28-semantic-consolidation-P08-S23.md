---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-29'
modified: '2026-08-29'
body_schema: 'body-v2'
body_hash: 'sha256:89bce07d91de7050cc2655481d653932c927477b4f82076bcb6f2af6150bffe1'
step_id: 'S23'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the two-character country code once across the 32 sites that state only its length, and rule on whether a charset check belongs on it

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/application/aggregation/_counterpart.py`
- `M` `src/cadrumo/application/aggregation/_foreign_assets.py`
- `M` `src/cadrumo/application/aggregation/_impatriado_income_ledger.py`
- `M` `src/cadrumo/application/aggregation/_irnr_income_ledger.py`
- `M` `src/cadrumo/application/invoices/_bulk_import.py`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/core/_period.py`
- `M` `src/cadrumo/core/country_code.py`
- `M` `src/cadrumo/core/tests/test_filing_year_single_declaration.py`
- `M` `src/cadrumo/domain/calculations/registry/counterpart_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/detail_record_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding296_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `M` `src/cadrumo/domain/invoices/_models.py`
- `M` `src/cadrumo/domain/modelos/_ledger_filing_snapshot.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_iva_ledger.py src/cadrumo/core/tests/test_period.py -n 0` -> `pass`
