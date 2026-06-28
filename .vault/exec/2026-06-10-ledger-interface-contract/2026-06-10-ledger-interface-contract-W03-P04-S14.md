---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S14'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Ledger Sort Enums

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Confirm `LedgerSortField` covers date, value_date, amount, description, lifecycle timestamps, classification timestamp, lifecycle state, and classification.
- Confirm `LedgerSortOrder` covers ascending and descending order.
- Keep enums in the core surface for reuse by CLI and projections.

## Outcome

Ledger sort field and order enums are available through the core surface.

## Notes

Verified by sort tests and documented command/schema conformance.