---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:559cd9191c0566972f730f01492d88ec2327cf577fdfc3c514c92db0fbb14c2b'
step_id: 'S08'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Unified Invoice Locale Leaves

## Scope

C4 ledger invoice unification reconciliation record for $(System.Collections.Hashtable.Step).

## Description

- Reconcile the already-landed unified invoice implementation against the approved C4 plan.
- Verify the relevant code and tests through focused C4 gates.
- Leave the AggregationSourceKind.INVOICE retirement chain open because registry consumers remain live.

## Outcome

The unified invoice locale section is present across the four locale catalogues.

## Notes

Verified with invoice application, operator-surface, business invoice CLI, business operation invoice, documented command, and JSON schema conformance tests. Registry-wide collection remains blocked by unrelated peer registry and wizard refactor errors.
