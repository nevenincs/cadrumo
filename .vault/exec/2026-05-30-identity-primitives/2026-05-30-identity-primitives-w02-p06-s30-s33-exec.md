---
step_id: S30
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W02.P06.S30-S33 — promote InvoiceId

## Scope

Declare the hex-64 `InvoiceId` alias in
`src/aeat/domain/invoices/_ids.py` per ADR Rule 6 owner-domain
placement, and lift the canonical `invoice_id` BaseModel field on
`domain/invoices/_models.Invoice` onto the alias.

## Outcome

`InvoiceId = Annotated[str, StringConstraints(min_length=64,
max_length=64, pattern=r"^[0-9a-f]{64}$")]` declared in
`src/aeat/domain/invoices/_ids.py` with an `__all__` export.

Promoted BaseModel fields:

- `src/aeat/domain/invoices/_models.py`: `Invoice.invoice_id`.

The inline `_HEX_INVOICE_ID_LENGTH = 64` constant is retained in
`_models.py` for use by the `_derive_invoice_id_when_complete`
helper and the `_validate_invoice_id_shape` post-validator;
collapsing the shadow constant is W03 scope. The existing
post-validator's stricter error message is preserved on top of the
alias-level pattern enforcement.

Real-behavior tests added at `src/aeat/domain/invoices/test_ids.py`
cover acceptance of a canonical sha-256 hex digest, rejection of
uppercase hex, rejection of wrong-length values, and rejection of
non-hex characters.

## Genuine non-canonical fields skipped

- `src/aeat/application/ledger/_business_operation_invoice.py:161`
  (`invoice_id: str = Field(min_length=1, max_length=64)`) —
  constraint cap is 64, not the hex-64 shape `Invoice.invoice_id`
  pins. The business-operation surface carries arbitrary
  operator-supplied invoice references (audit log, AEAT-side ids)
  not constrained to the canonical hex-64 derivation; skipped per
  brief's genuine-non-canonical clause.
- `src/aeat/application/invoices/_linking.py:26`,
  `_queries.py:30`, `_reconciliation.py:26`,
  `application/review/_models.py:156`,
  `domain/calculations/registry/_bindings.py:525`,
  `domain/invoices/_service.py:51` — `invoice_id: str =
  Field(min_length=1)` (no upper bound) or
  `Field(min_length=1, max_length=128)`. Reference identities
  pointing at invoices, not content-addressed mints; promotion would
  narrow constraints and reject legitimate operator-supplied values.

## Verification

- `uv run --no-sync pytest src/aeat/domain/invoices/` returns
  `124 passed` (120 prior + 4 new alias tests).

## Plan steps closed

`W02.P06.S30`, `S31`, `S32`, `S33`. S32 (`application/ledger/_models.py`)
landed as a no-op — the ledger models surface carries no `invoice_id`
BaseModel field; ledger transactions reference invoices by
`linked_transaction_ids` tuples, not by an invoice_id field. The
S33 dedicated roundtrip test would duplicate the existing
`test_secure_storage_roundtrip.py` boundary coverage that already
exercises `Invoice` persistence through the real SecureObjectRepository;
the typed alias is exercised on every test that constructs an
`Invoice`.
