---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S05'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Single ID Resolver

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Confirm lifecycle CLI verbs use the shared ledger `_resolve_id` helper.
- Keep one authoritative id-resolution path for single-row ledger verbs.
- Verify no duplicate lifecycle resolver remains in the ledger CLI modules.

## Outcome

The duplicate resolver body is collapsed to the shared helper used by the ledger command surface.

## Notes

This records prior landed implementation that was already checked in the plan without an exec record.