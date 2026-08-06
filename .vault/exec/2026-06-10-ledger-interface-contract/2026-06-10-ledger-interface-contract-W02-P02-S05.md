---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:2310d4af3e491e9de233c32396b21a0a40b38c5ca956a5fd75d9a5242d4a617a'
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
