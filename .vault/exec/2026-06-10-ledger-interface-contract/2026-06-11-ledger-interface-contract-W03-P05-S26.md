---
tags: ['#exec', '#ledger-interface-contract']
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:f8b8cf773adcedac0ddb6296721ebc3ea1840a50a320490a12b1c5de9411aba7'
step_id: 'S26'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# W03.P05.S26 Invoice List Rows Typed

Scope: close the unified invoice list row typing remainder.

## Description

- Change the shared business-invoice list result to use `BusinessInvoiceRecordPayload` rows.
- Add constructor coverage for the invoice row payload.
- Verify the JSON schema conformance suite after the shape change.

## Outcome

`ledger invoice list` rows now validate as the same strict typed payload used by invoice mutation and view results.

## Notes

This follows the already-landed C4 unified `invoice --kind issued|received` surface.
