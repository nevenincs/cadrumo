---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:daeda4533a96d1c8e5e425863245c8969e5df613a3bfc21c91b462a93e03438a'
step_id: 'S16'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Invoice Mutation Verbs

## Scope

C4 ledger invoice unification reconciliation record for $(System.Collections.Hashtable.Step).

## Description

- Reconcile the already-landed unified invoice implementation against the approved C4 plan.
- Verify the relevant code and tests through focused C4 gates.
- Leave the AggregationSourceKind.INVOICE retirement chain open because registry consumers remain live.

## Outcome

The unified invoice app implements add, view, update, and remove with mandatory `--kind` and unified result schemas.

## Notes

Verified with invoice application, operator-surface, business invoice CLI, business operation invoice, documented command, and JSON schema conformance tests. Registry-wide collection remains blocked by unrelated peer registry and wizard refactor errors.
