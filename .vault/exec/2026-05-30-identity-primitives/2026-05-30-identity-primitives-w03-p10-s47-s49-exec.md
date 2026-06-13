---
step_id: S47
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W03.P10.S47-S49 — delete _HEX_*_LENGTH constants

## Scope

Delete the three `_HEX_*_LENGTH = 64` shadow constants enumerated in
the ADR Consequences "Shadow declarations that must collapse"
section: `_HEX_TRANSACTION_ID_LENGTH` in `domain/invoices/_service.py`
and `domain/invoices/_models.py`, `_HEX_INVOICE_ID_LENGTH` in
`domain/invoices/_models.py`, and `_HEX_WORK_UNIT_ID_LENGTH` in
`domain/modelos/_work_unit.py`. Replace consumer pydantic field
declarations with the typed alias from the owning `_ids.py`; inline
the literal `64` at helper-function consumers per the brief's
escape clause.

## Outcome

`src/aeat/domain/invoices/_service.py`:
- `ReconciliationSuggestion.transaction_id` and
  `LinkInconsistency.transaction_id` consume `TransactionId` from
  `domain/modelos/_ids` directly.
- `link_transaction` hex-length guard inlines the literal `64`.

`src/aeat/domain/invoices/_models.py`:
- `_HEX_TRANSACTION_ID_LENGTH` and `_HEX_INVOICE_ID_LENGTH` both
  deleted; `Invoice.invoice_id` already consumes the `InvoiceId`
  alias (lifted in W02.P06.S31). The redundant
  `_validate_invoice_id_shape` post-validator removed since the
  alias enforces the hex-64 contract at construction.
- `_is_hex_digest` helper consumers in `_normalise_invoice_payment_id`
  and `_normalise_linked_transaction_ids` inline the literal `64`.

`src/aeat/domain/modelos/_work_unit.py`:
- `_HEX_WORK_UNIT_ID_LENGTH` deleted. The constant had no remaining
  consumers; `WorkUnit.work_unit_id` already consumes the
  `WorkUnitId` alias.

`src/aeat/domain/invoices/test_service.py`:
- Test-side import of `_HEX_TRANSACTION_ID_LENGTH` replaced with the
  literal `64`; docstring updated to refer to the `TransactionId`
  alias as the single home of the constraint.

## Verification

- `uv run --no-sync pytest src/aeat/domain/invoices/` returns
  `124 passed`.
- `uv run --no-sync pytest src/aeat/domain/modelos/` returns
  `147 passed`.

## Plan steps closed

`W03.P10.S47`, `S48`, `S49`.
