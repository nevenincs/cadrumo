---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:e74d99c1c3f63e58bb0bc03aaf90ac05003e11c7ac894d17431426f8186022aa'
step_id: 'S17'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Sort Stability Tests

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Add real-behaviour tests for equal primary sort keys.
- Assert transaction-id tie-break is ascending under both primary sort orders.
- Exercise sorting through a real encrypted catalogue repository.

## Outcome

Sort stability and projection wiring are covered by real-behaviour tests.

## Notes

The missing-key case now uses optional `value_date`, not lifecycle timestamps.
