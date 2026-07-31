---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:a80e70d2b68810c510f09a40ea1133c5c09c15aa2cc215f2b61ca7d0f5de49af'
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
