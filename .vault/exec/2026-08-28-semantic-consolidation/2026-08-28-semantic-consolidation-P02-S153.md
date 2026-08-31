---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:9998b4144b76e635a7d3f6167b092ac3c71ca8dbb8cab47115721c620eb70fae'
step_id: 'S153'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Bound the purchase-invoice evidence money fields on the record and its patch, after tracing the two that reach a renta deduction

## Scope

- `src/cadrumo/application/ledger/evidence.py`

## Changes

- `M` `src/cadrumo/application/ledger/evidence.py`
- `verify:` record now refuses iva_rate 210 and -5, taxable_base -5, iva_amount -5; accepts 21 and 0
- `verify:` patch refuses a negative taxable_base
- `verify:` `pytest application/ledger/tests -k evidence -n 0 -m ""` -> 249 pass, 6 pre-existing failures

## Notes

Reported as a display-only exposure: a persisted evidence record whose
`iva_rate` took any Decimal at all, with no calculation consumer found. Verifying
it made the finding bigger in two directions.

First, it is not one field. `taxable_base` and `iva_amount` on the same record
were equally unbounded, and those two are NOT display-only: the reconciliation
projection at `application/aggregation/_renta_ledger.py:722` copies them into a
renta deductible-expense observation. A negative taxable base persisted on
evidence reaches a deduction. The report had itself noted the projection carries
those two fields; what it did not do was connect that to the unbounded source.

Second, it is not one model. The same three fields are declared identically on
`PurchaseInvoiceEvidencePatch`, so both the record and its update path took any
Decimal. This is the create/patch pairing again, but not a DIVERGENCE -- both
sides were equally unguarded, which is why the sibling scan in S152 would never
have found it: that scan looks for the two sides disagreeing.

The first edit attempt asserted the field block appeared once and refused when it
found two. That refusal was the useful part -- it stopped a replace that would
have silently patched whichever copy came first and left the other, which is
precisely how the divergences this campaign keeps finding get created.

`iva_rate` takes the percentage scale per its own docstring, so it reads
`Percentage`; the two amounts read `NonNegativeDecimal`, the ledger's standing
rule that an amount is a magnitude.
