---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:143ba18b73005b0ee3946eef909f08e9dd08faf1b1e2b90c32af1179f2f11d06'
step_id: 'S09'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Invoice Locale Parity

## Scope

C4 ledger invoice unification reconciliation record for $(System.Collections.Hashtable.Step).

## Description

- Reconcile the already-landed unified invoice implementation against the approved C4 plan.
- Verify the relevant code and tests through focused C4 gates.
- Leave the AggregationSourceKind.INVOICE retirement chain open because registry consumers remain live.

## Outcome

The C4 verification accepted the unified locale surface; no duplicate command leaves remain for the split invoice nouns.

## Notes

Verified with invoice application, operator-surface, business invoice CLI, business operation invoice, documented command, and JSON schema conformance tests. Registry-wide collection remains blocked by unrelated peer registry and wizard refactor errors.
