---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b69e7d3132b2be8b232c9019bfed524e3732ee46a5b96d919d2235a19c86418b'
step_id: 'S32'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# retype classified invoice-id pydantic model fields onto `InvoiceId` in the invoices packages

## Scope

- `src/cadrumo/application/invoices/_linking.py`
- `src/cadrumo/application/invoices/_queries.py`
- `src/cadrumo/application/invoices/_reconciliation.py`
- `src/cadrumo/domain/invoices/_decomposition.py`
- `src/cadrumo/domain/invoices/_service.py`
- `src/cadrumo/domain/invoices/tests/test_decomposition.py`
- `src/cadrumo/domain/invoices/tests/test_service.py`

## Description

- The row's own action text names BOTH "the invoices application and
  domain packages", while its formal scope glob lists only
  `application/invoices/`. Measured both (`application/invoices/` AND
  `domain/invoices/`) rather than trusting the narrower glob, per the
  campaign's precedent from `W04.P06.S31` of trusting the row's own prose
  over a possibly-incomplete scope field.
- Re-derived the denominator with an AST probe over a fresh `git archive
  HEAD` extraction of both packages, model-field-only, `tests/` excluded.
  Found 7 raw matches: 6 bare `str` sites across both packages, plus
  `Invoice.invoice_id` (`domain/invoices/_models.py`) already
  `InvoiceId`-typed.
- Traced every one of the 6 bare sites to its construction site(s) before
  retyping:
  - `InvoiceTransactionLinkResult.invoice_id` (`_linking.py`) — retyped.
    Its one construction site only runs after a find-or-raise lookup
    (`updated_invoices.get(invoice_id)`, raising `InvoiceLinkError` on a
    miss) already confirmed the value names a real catalogued invoice.
  - `InvoiceListRow.invoice_id` (`_queries.py`) — retyped, fed from
    `invoice.invoice_id` off an already-typed `Invoice`.
  - `ReconciliationSkippedSuggestion.invoice_id` (`_reconciliation.py`) —
    retyped, fed from `suggestion.invoice_id`
    (`ReconciliationSuggestion.invoice_id`, itself traced clean below).
  - `InvoiceDecomposition.invoice_id` (`_decomposition.py`) — retyped.
    `decompose_invoice`'s own docstring states its `invoice` parameter is
    "an already-valid invoice record"; both construction sites feed
    `invoice.invoice_id`.
  - `ReconciliationSuggestion.invoice_id` (`_service.py`) — retyped, one
    construction site, `invoice.invoice_id` from an unlinked catalogue
    invoice.
  - `LinkInconsistency.invoice_id` (`_service.py`) — LEFT BARE, a real and
    load-bearing exclusion. `verify_link_consistency` builds it from TWO
    branches: the INVOICE_ONLY branch feeds `invoice.invoice_id` (safe),
    but the TRANSACTION_ONLY branch feeds `transaction.invoice_id` —
    `domain.transactions.Transaction`'s own bare, unconstrained
    `str | None = None` foreign key. This function's entire purpose is to
    detect a transaction whose `invoice_id` does NOT resolve to a real
    invoice (`invoice = invoices.get(transaction.invoice_id); if invoice
    is None or ...`). Retyping the diagnostic field to `InvoiceId` would
    make constructing the INCONSISTENCY RECORD raise on exactly the
    dangling reference it exists to report — the same shape as
    `W04.P06.S29`'s `BulkClassifyFailure` exclusion and `W04.P06.S30`'s
    `IvaLedgerAggregationIssue` exclusion. Documented inline with a code
    comment.
- Adjacent finding, NOT fixed (out of this row's `invoice_id`-only scope):
  `InvoiceTransactionLinkResult.transaction_id` and
  `ReconciliationSkippedSuggestion.transaction_id` are ALSO bare `str`,
  in the SAME two files this row touched, but neither `application/ledger/`
  (`W04.P06.S29`'s scope) nor `application/invoices/` (this row's own
  `invoice_id`-only gate) covers a `transaction_id` retype here. Recorded,
  not executed.
- Fixed 3 tests broken by the retype, all placeholder-literal fixtures
  (`"abc"`, `"INV-1"`) predating the retype: two `InvoiceDecomposition`
  direct constructions in `test_decomposition.py` and one
  `ReconciliationSuggestion` construction in `test_service.py`, all
  replaced with real hex-64 values (`test_service.py` already carried a
  reusable `_SAMPLE_HEX_64` constant for its `transaction_id` fixtures;
  reused it for `invoice_id` rather than adding a second one).

## Outcome

COMPLETE. 5 of 6 classified sites retyped; 1 left bare with a traced,
demonstrated construction-site reason, documented both in this record and
inline in the source. One adjacent out-of-scope finding recorded, not
fixed. `ruff check`, `ruff format --check`, `basedpyright` clean on all 5
touched production files. Full `application/invoices/tests/` +
`domain/invoices/tests/` suite: 374 passed, 0 failures. Targeted CLI sweep
(`entrypoints/cli/tests/ -k invoice`): 20 passed, 1 pre-existing unrelated
failure (the already-flagged `matched_rule_id` pattern mismatch, confirmed
by content — no `invoice_id` reference — and file cleanliness).

## Notes

No incidents. Two of the three "decline rather than force" style findings
in this row's own record (`LinkInconsistency.invoice_id`'s exclusion, and
the two-file `transaction_id` adjacent finding) came directly from tracing
construction sites rather than trusting field names, the same discipline
`W04.P06.S29`/`S30`/`S31` established.
