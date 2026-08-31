---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f65f42a798b61110558cb65eef1774104d92bc6e157cf347cb92ded0b2293763'
step_id: 'S04'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Reconcile the ledger payload modules onto canonical transaction, invoice, counterparty and rule aliases

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/domain/invoices/validators.py`
- `M` `src/cadrumo/domain/invoices/models.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_catalogue_invoice_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`
- `verify:` dispatch probed at ES/valid, ES/garbage, DE/valid, None/garbage, None/valid
- `verify:` `pytest domain/invoices + payload gate -n 0 -m ""` -> pass (242 + 7)
- `verify:` outstanding payload modules 5 -> 4

## Notes

The last ledger payload module was held open by one `model_validator`, and the
gate was right to hold it. The validator does delegate its checks to the
canonical identity validators -- but it decided WHICH regime applies with its own
`if country == "ES"`, and the invoice normaliser decided the same thing with a
mapping and a default. Same rule, two spellings, in a domain model and a wire
projection.

Probed before extracting, and the two populations differ in a way worth keeping:
the domain maps an ABSENT country to a pass-through, so a garbage identifier is
accepted when no country is declared. That is deliberate -- a factura
simplificada may carry no counterparty country, and with no country there is no
regime to check against. The CLI payload's country is required, so it never
reaches that branch. Not a divergence on shared input, but the same rule written
twice all the same.

`validate_counterparty_tax_id` now carries it, beside the two validators it
dispatches to, with the absent-country pass-through documented as the deliberate
half rather than an oversight.

This completes the ledger family the step names. `_ledger_payloads.py` and
`_ledger_business_payloads.py` were reconciled earlier in the campaign; this was
the third.
