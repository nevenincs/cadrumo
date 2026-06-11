---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
step_id: 'S22'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Typed Import Transaction References

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Define `LedgerImportTransactionRefPayload`.
- Type imported, skipped, and likely-duplicate transaction reference lists.
- Validate import result construction and schema registration.

## Outcome

Ledger import result reference lists are typed payload lists.

## Notes

Verified by payload and schema conformance gates.