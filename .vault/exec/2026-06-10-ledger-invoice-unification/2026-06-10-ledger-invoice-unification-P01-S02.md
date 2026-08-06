---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:9dd20725b041f6e5e79753953df28e33426b7e0b44b6651b9ac1464ca1840a7c'
step_id: 'S02'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Invoice Direction Mapping Contract

## Scope

C4 ledger invoice unification reconciliation record for $(System.Collections.Hashtable.Step).

## Description

- Reconcile the already-landed unified invoice implementation against the approved C4 plan.
- Verify the relevant code and tests through focused C4 gates.
- Leave the AggregationSourceKind.INVOICE retirement chain open because registry consumers remain live.

## Outcome

`invoice_direction_to_source_kind` is a named contract in the invoice source resolver and the resolver call site uses it.

## Notes

Verified with invoice application, operator-surface, business invoice CLI, business operation invoice, documented command, and JSON schema conformance tests. Registry-wide collection remains blocked by unrelated peer registry and wizard refactor errors.
