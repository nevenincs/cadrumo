---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:8cbb6612f8c41d28bb344c3767c293f076078af8adef819776869cddda3be9c6'
step_id: 'S229'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unused slim InvoiceListRow projection, its two zero-consumer catalogue row builders, and the two self-tests that only preserve them; retain the canonical rich Invoice aggregate, the live ledger.invoice.list payload, and the production-used repository link-consistency query and its real storage-boundary test.

## Scope

- `Application invoice catalogue reads and focused tests`
- `live CLI invoice list projection`
- `accepted canonical invoice structure decision`
- `exact symbol signal`
- `focused invoice gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/application/invoices/catalogue_reads.py`
- `M` `src/cadrumo/application/invoices/tests/test_queries.py`
- `M` `src/cadrumo/application/invoices/__init__.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/invoices/catalogue_reads.py src/cadrumo/application/invoices/tests/test_queries.py src/cadrumo/application/invoices/__init__.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s229 src/cadrumo/application/invoices/tests/test_queries.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s229-cli src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py src/cadrumo/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "not unit" --basetemp .tmp/pytest-s229-cli-held src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py src/cadrumo/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact audit exits 1 on the remaining backlog, as designed. This step reduced reachable-module unused-symbol findings from 305 to 304 while leaving 51 unreachable modules and four orphaned test modules unchanged. Three production names were removed, but only `list_invoice_rows` was an exact finding; the DTO and private projector were already cleared by other audit rules. The retained repository link query has a production caller and its two focused consistency tests pass.
