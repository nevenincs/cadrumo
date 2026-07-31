---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:8365cc2887c1c18b1119e3835c622c0e85d2ee7b51b33dedaec04c35379ea7bc'
step_id: 'S14'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Invoice Surface Collection

## Scope

C4 ledger invoice unification reconciliation record for $(System.Collections.Hashtable.Step).

## Description

- Reconcile the already-landed unified invoice implementation against the approved C4 plan.
- Verify the relevant code and tests through focused C4 gates.
- Leave the AggregationSourceKind.INVOICE retirement chain open because registry consumers remain live.

## Outcome

Operator-surface and invoice CLI collection completed in the C4 verification sweep.

## Notes

Verified with invoice application, operator-surface, business invoice CLI, business operation invoice, documented command, and JSON schema conformance tests. Registry-wide collection remains blocked by unrelated peer registry and wizard refactor errors.
