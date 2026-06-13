---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S31'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Participation Payload Slot

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Declare `LedgerTransactionParticipationPayload` as a strict output schema slot.
- Document the slot as reserved for C7 participation read output.
- Keep the type available in the ledger schema module.

## Outcome

The C7 participation payload slot exists in the ledger CLI schema surface.

## Notes

Verified by payload/schema import and conformance checks.