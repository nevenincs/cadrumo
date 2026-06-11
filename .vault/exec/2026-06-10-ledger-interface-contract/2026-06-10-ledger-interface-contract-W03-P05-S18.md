---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
step_id: 'S18'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Ledger List Row Payload

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Define `LedgerListRowPayload` as a strict output schema.
- Carry row identity, display fields, review status, lifecycle state, grouping, and timestamps.
- Project list rows from the application review payload plus list-specific fields.

## Outcome

Ledger list rows have a typed schema instead of an unstructured row dictionary.

## Notes

Verified by payload and schema conformance gates.