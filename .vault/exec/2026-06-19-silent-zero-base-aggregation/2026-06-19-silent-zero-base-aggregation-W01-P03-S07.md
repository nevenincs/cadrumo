---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S07'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# model recargo de equivalencia on the transaction (recargo rate + recargo cuota alongside the IVA fields, or a dedicated recargo classification) grounded in ley-37-1992:art-161 against the bundled corpus - the prerequisite domain change before any recargo binding

## Scope

- `src/aeat/domain/iva/_schema.py`
- `src/aeat/domain/iva/_schema.py`

## Description

Modelled recargo de equivalencia on the transaction so a supplier's recargo
charged on a repercutido sale can be carried into the ledger.

- Added a non-negative `recargo_amount` field to the `Transaction` model (the
  recargo cuota the supplier charged), validated alongside the IVA tax amounts and
  carried through the encrypted JSON-envelope persistence (roundtrips additively).
- Added a CLI input surface `aeat app ledger add --recargo-amount`, the
  `ManualLedgerTransactionCommand` / `ManualLedgerTransactionPatch` field, the
  action wiring (command-to-transaction payload and patch-apply path, with recargo
  cleared when a row leaves a tax-relevant classification), and the four-language
  locale help key via the locale CLI.

Files: `src/aeat/domain/transactions/_models.py`,
`src/aeat/application/ledger/_models.py`,
`src/aeat/application/ledger/_actions_manual.py`,
`src/aeat/entrypoints/cli/_ledger.py`, `src/aeat/locales/*.yml`.

## Outcome

The transaction roundtrip and ledger action/CLI suites pass (324 + 140). The
existing retailer-side `RECARGO_EQUIVALENCIA` category is unchanged; recargo rides
as an additive amount on a normal taxable repercutido sale, the supplier-side flow
the M303 recargo cuotas need.

## Notes

The research below S07 disproved reusing the retailer-side category; this models
the supplier side as the recargo_amount carrier instead.
