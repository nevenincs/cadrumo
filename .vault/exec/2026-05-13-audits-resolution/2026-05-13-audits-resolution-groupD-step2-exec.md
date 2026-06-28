---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-eliminate-shims-audit]]"
---

# audits-resolution group-d step-2

## scope

Plan row D2: resolve the three borderline tautological assertions
from the code audit's `_iva_classification` and
`_ledger_iva_aggregation_binding` cluster.

## changes

`src/aeat/domain/invoices/test_iva_classification.py:239-241`: the
three single-observation per-rate identity passthroughs gain
structural wiring assertions (key presence in the binding result)
before the existing value assertions. The value assertions are now
documented as routing-id verifications under the rule's identity-
round-trip carve-out — each observation provides the iva_amount
directly, so the equality verifies the resolver threads the value
through the correct binding key, not the resolver's arithmetic.

`src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py:256`:
the 210+100=310 hand-summed assertion flips to a filter-contract
verification pair: `cuota < Decimal("999")` (RECARGO_EQUIVALENCIA
observation correctly excluded) AND `cuota > Decimal("210")` (both
matching observations contributed, not just one). The filter
behaviour IS what the test pins; the precise arithmetic is verified
against AEAT workbook parity.

The `test_ledger_renta_expense_binding.py:103-106` instance is
explicitly left for the concurrent ledger-renta-pipeline workstream
per the off-limits clause.

## verification

`pytest src/aeat/domain/invoices/test_iva_classification.py
src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py
-q` returns 39 passed.
