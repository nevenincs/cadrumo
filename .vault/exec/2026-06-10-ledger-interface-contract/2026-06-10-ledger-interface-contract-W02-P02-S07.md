---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
step_id: 'S07'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Lifecycle Positional ID

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Confirm lifecycle verbs accept positional transaction ids.
- Remove the legacy option-form id input from archive, stash, restore, remove, split, and merge surfaces.
- Verify documented command conformance covers the converted lifecycle verbs.

## Outcome

Lifecycle single-subject verbs follow the positional id convention.

## Notes

This records prior landed implementation that was already checked in the plan without an exec record.