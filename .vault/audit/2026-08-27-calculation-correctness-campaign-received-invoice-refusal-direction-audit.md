---
tags:
  - '#audit'
  - '#calculation-correctness-campaign'
date: '2026-08-27'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:dfb7a37d492984487dbc1ce16cdb2f054657a42acb1ba77aa34955dd589c510e'
related: []
---

# `calculation-correctness-campaign` audit: `a purchase-invoice guard refuses citing under-declaration on the over-payment direction`

## Scope

## Findings

## Recommendations

## Finding

`application/aggregation/_modelo_bindings.py` refuses the whole filing when a
withheld invoice's cuota is not carried by the transaction ledger
(`_uncovered_withheld_invoice_cuota`, raised around line 1324 with reason
`invoice_deduction_authority_missing_from_transaction_ledger`).

Its stated criterion is under-declaration. The docstring says a positive
result "means the ledger is genuinely short by at least this much and the
filing would under-declare".

But the population it fires on is input-side only. `deduction_authority_missing`
is set exactly when:

    invoice.kind is InvoiceKind.RECEIVED
    and any(line.iva_amount > 0 for line in invoice.lines)
    and deduction_authority is None

A RECEIVED invoice carries IVA soportado. If the ledger does not carry it, the
taxpayer deducts LESS input IVA than the invoice would support: they over-pay.
That is the opposite direction from the one the guard says it is protecting.

## Why this is worth a decision rather than a patch

The surrounding comment already draws the distinction the code then does not
keep: "Withholding an unauthorised input row is unconditional; REFUSING the
whole filing over it is not." Withholding is what stops an invented deduction
reaching a casilla. Refusing additionally blocks a filing whose declared output
tax is unaffected by the missing purchase evidence.

`no-silent-under-declaration` names this exact shape:

    Watch the unwatched direction too. This apparatus is built against
    under-declaration ... deliberately probe the opposite direction -- the
    structural tell is a RESTRICTIVE PROVISION USED AS A DEFAULT.

## Corroboration

`test_iva_source_mesh_withholds_received_invoice_without_deduction_authority`
encodes the opposite expectation: a received invoice with an empty ledger
should be WITHHELD with a diagnostic, not refused. It asserts the diagnostic
text and remedy, so it was written deliberately. It is long-standing red --
still failing at `0813f00e74` and `15b99fcd39` -- so this is not a fresh
regression.

The sibling case that DOES refuse
(`reason == "invoice_domestic_iva_not_in_transaction_ledger"`) is the
output-side one, where a ledger shortfall genuinely under-declares.

## Not changed here

Whether a purchase invoice absent from the ledger should block a filing is a
tax-semantics decision, not a test repair. Making the test pass by relaxing the
guard, or making the guard pass by rewriting the test, would each settle that
question silently. Both directions need the owner.

## Status

Open. One test red, and it is red about something real.
