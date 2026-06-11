---
tags: ['#exec', '#ledger-interface-contract']
date: '2026-06-11'
step_id: 'S28'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# W03.P05.S28 Evidence List Rows Typed

Scope: close the purchase-invoice evidence list typing remainder.

## Description

- Change `EvidenceListResult.rows` to a list of `EvidenceRecordPayload`.
- Add constructor coverage for an evidence list row, including the encrypted attachment id field.
- Verify the ledger schema conformance gate after the change.

## Outcome

Evidence list rows now validate through the same strict evidence record payload used by add, view, update, and remove.

## Notes

The payload keeps `source_path` as provenance only; stored evidence bytes remain in the secure attachment store.
