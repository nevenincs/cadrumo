---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:af2cd0bc8f8d7c712f96a3bf9ab89e0f906549cc64859f556139ca537772b68f'
step_id: 'S51'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Rewire extraction recargo aggregation and inventory defaults

## Scope

- `src/cadrumo/application/ledger and src/cadrumo/application/aggregation and src/cadrumo/domain/contribuyente/inventory`

## Changes

- `M` `src/cadrumo/application/ledger/invoice_extraction_authority.py`
- `M` `src/cadrumo/application/ledger/tests/test_invoice_extraction_authority.py`
- `M` `src/cadrumo/domain/contribuyente/inventory/records.py`
- `M` `src/cadrumo/domain/contribuyente/inventory/tests/test_acquisition_cost.py`
- `verify:` `uv run ruff check src/cadrumo/application/ledger/invoice_extraction_authority.py src/cadrumo/application/ledger/tests/test_invoice_extraction_authority.py src/cadrumo/domain/contribuyente/inventory/records.py src/cadrumo/domain/contribuyente/inventory/tests/test_acquisition_cost.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/ledger/invoice_extraction_authority.py src/cadrumo/domain/contribuyente/inventory/records.py` -> `pass`
