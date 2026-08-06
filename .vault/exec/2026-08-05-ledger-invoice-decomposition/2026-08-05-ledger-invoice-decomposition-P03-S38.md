---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
step_id: 'S38'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Let the income aggregation read a linked sales invoice for its base, cuota and retencion, following the derive-on-read shape the expense pipeline already proves

## Scope

- `src/cadrumo/application/aggregation/_renta_income_ledger.py`

## Description

NOT IMPLEMENTED. This record is the design, written at the point the coordinator
ran out of context to land it coherently. Everything below is measured at HEAD,
not proposed from memory.

The change must land whole. An evidence resolver that exists but is not threaded
is dead capacity, which this codebase bars outright, and a half-wired landing
broke HEAD for a peer earlier in this campaign.

## Outcome

### The defect, demonstrated

Running the real path with no test doubles:

```
BEFORE link : taxable_base = None
AFTER  link : invoice_id = inv-F-2024-001   taxable_base = None
casilla 01  : 1060.00   grounding = cash_fallback   withheld = 0
```

A linked, matched invoice leaves casilla 01 on the credited cash. `link_invoice`
in the transactions service carries identity and never content.

### The precedent to mirror

The expense pipeline already implements derive-on-read. Its evidence resolver
applies six guards before trusting a linked invoice, then returns a payload of
the invoice's own figures, and a per-field accessor gives the invoice
precedence with the transaction field as fallback.

The guards, in order: the invoice belongs to the active bucket; its kind is the
one this side expects; the link is reciprocal, meaning the transaction id appears
in the invoice's own linked ids; exactly one transaction is linked; the linked
amount corresponds to the invoice; then the payload.

### The one guard that must differ, and it is the whole point

The expense side asserts `transaction_amount == invoice.grand_total`. An expense
row pays the full contraprestacion.

**The income side must not.** A sales invoice subject to retencion is paid NET:
the payer withholds and remits it, so the bank credit is
`grand_total - retention_amount`. Asserting equality against `grand_total` would
reject exactly the invoices this Step exists to ground, and asserting it against
cash without the retencion term would accept a mismatched pair.

The correspondence to assert is therefore:

```
transaction_amount == invoice.grand_total - (invoice.retention_amount or 0)
```

Getting this backwards is the failure mode with real consequences: it would
either refuse every net-paid professional invoice, or silently accept an invoice
that does not describe the payment.

### Insertion point

`_renta_income_ledger.py` derives `taxable_base_amount` from
`transaction.taxable_base` alone immediately before constructing the
observation, and sets the grounding marker from whether that value is present.
The resolved invoice base takes precedence there, which means a grounded row
also stops reporting `CASH_FALLBACK` and stops raising the ungrounded advisory —
correctly, since the substrate now exists.

The retencion follows the same shape: `Invoice.retention_amount` exists today and
reaches nothing. Preferring it over the bounded gross-minus-cash inference is
strictly better, because a declared figure beats a derived one — that ordering is
already the ADR's ruling on retencion, honoured elsewhere and not here.

### Plumbing required

The income resolver holds only a transaction repository. The expense one takes an
invoice repository as well. Both income entry points — the quarterly path and the
annual Modelo 100 path — need it, and the single production call site constructs
the aggregator by choosing between them, so both must gain the parameter together
or the annual and quarterly halves would ground differently. That asymmetry is
precisely what this campaign has been removing.

### What the new issue reasons must carry

A mismatch is refused with a traceable reason, never silently applied. The expense
side spells these per failure — wrong bucket, wrong kind, non-reciprocal link,
multi-transaction evidence, amount mismatch — and the income side needs the
equivalents. A single generic reason would lose which check failed, which is the
information an operator needs to fix the link.

## Notes

**Authorisation.** This changes the figures a return carries. The application
never files — it builds, validates and exports for a human to file — and the
change moves a demonstrably wrong number to a right one, so the risk is bounded.
The coordinator nonetheless left it for the operator rather than reversing a
position it had already stated twice.

**Why it is not a design question.** Three shapes were considered open — copy on
link, derive on read, copy on confirmation. The expense pipeline settles it:
derive-on-read is the established pattern, and it already handles the two hazards
that made the choice look hard. Nothing is copied, so no stale figure can outlive
a corrected invoice; and a link whose amounts do not correspond is refused rather
than applied, so no filed figure is silently rewritten.

**The asymmetry this closes.** The expense pipeline surfaced a missing base while
the income pipeline silently folded cash — that opened this campaign. The expense
pipeline reads a linked invoice while the income pipeline ignores it — that is the
same asymmetry a second time, on the same two pipelines, and the income side is the
one carrying the central figure of the return.
