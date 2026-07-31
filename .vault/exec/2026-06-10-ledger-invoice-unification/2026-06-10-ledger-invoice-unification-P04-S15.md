---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:64351852aef7eff2fd78e07b299e2e40271bc87a37593521b9c6e2538017e48f'
step_id: 'S15'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Unified Invoice CLI App

## Scope

C4 ledger invoice unification reconciliation record for $(System.Collections.Hashtable.Step).

## Description

- Reconcile the already-landed unified invoice implementation against the approved C4 plan.
- Verify the relevant code and tests through focused C4 gates.
- Leave the AggregationSourceKind.INVOICE retirement chain open because registry consumers remain live.

## Outcome

The ledger business-invoice CLI exposes one `invoice_app` and routes `--kind issued|received` through `invoice_direction_to_source_kind`.

## Notes

Verified with invoice application, operator-surface, business invoice CLI, business operation invoice, documented command, and JSON schema conformance tests. Registry-wide collection remains blocked by unrelated peer registry and wizard refactor errors.
