---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:1b503c1225dbc9537062f995a79ce1ac0657d7debf9ef555598af4866663fffe'
step_id: 'S26'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Invoice List No-Kind Guard

## Scope

C4 ledger invoice unification reconciliation record for $(System.Collections.Hashtable.Step).

## Description

- Reconcile the already-landed unified invoice implementation against the approved C4 plan.
- Verify the relevant code and tests through focused C4 gates.
- Leave the AggregationSourceKind.INVOICE retirement chain open because registry consumers remain live.

## Outcome

`test_invoice_list_without_kind_returns_both_kinds` verifies the bare list path returns both source kinds.

## Notes

Verified with invoice application, operator-surface, business invoice CLI, business operation invoice, documented command, and JSON schema conformance tests. Registry-wide collection remains blocked by unrelated peer registry and wizard refactor errors.
