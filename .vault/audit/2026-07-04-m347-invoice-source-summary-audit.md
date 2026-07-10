---
tags:
  - '#audit'
  - '#m347-invoice-source-summary'
date: '2026-07-04'
modified: '2026-07-04'
related: []
---

# `m347-invoice-source-summary` audit: `M347 invoice-source summary review`

## Scope

M347 invoice-source summary bindings and resolver behaviour were audited after the stale
`ledger_transaction` approach was replaced with the already-enrolled invoice family.
The review covered the registry binding, invoice resolver activation, gross-total
threshold semantics, the counterpart negative guard, and path-scoped verification.

## Findings

No findings. The M347 summary route uses invoice-owned sources rather than reserved
counterpart sources; the invoice resolver activates both collectible and payable
observations for the M347 summary record, and the binding path thresholds and sums
gross invoice totals through `invoice_total_amount`.

## Recommendations

Keep the reserved `ledger_transaction` / `purchase_invoice_evidence` counterpart-provider
promotion blocked until their persisted records carry the tax identity and total facts
required for M347. Current verification for this slice passed path-scoped ruff and tests;
the global source-enrollment gate remains blocked by unrelated Modelo 145 placeholder
registry data that lacks workbook parity coverage and casillas.
