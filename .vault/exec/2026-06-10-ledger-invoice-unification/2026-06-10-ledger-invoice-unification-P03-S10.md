---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
step_id: 'S10'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Remove Duplicate Invoice Payloads

## Scope

C4 ledger invoice unification reconciliation record for $(System.Collections.Hashtable.Step).

## Description

- Reconcile the already-landed unified invoice implementation against the approved C4 plan.
- Verify the relevant code and tests through focused C4 gates.
- Leave the AggregationSourceKind.INVOICE retirement chain open because registry consumers remain live.

## Outcome

The old payable/collectible invoice result classes are absent from the ledger payload schema module.

## Notes

Verified with invoice application, operator-surface, business invoice CLI, business operation invoice, documented command, and JSON schema conformance tests. Registry-wide collection remains blocked by unrelated peer registry and wizard refactor errors.