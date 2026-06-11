---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-11'
step_id: 'S15'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# Project Ledger List Sort

## Scope

C5 ledger interface contract execution record for $(System.Collections.Hashtable.Step).

## Description

- Thread `sort_by` and `sort_order` through `project_ledger_list`.
- Apply stable sorting after filters with transaction id as the final tie-break.
- Preserve optional-key handling for axes such as `value_date` without nullable lifecycle timestamps.

## Outcome

Ledger list projection supports deterministic sorting with stable transaction-id tie-breaks.

## Notes

Focused list-sort tests passed against the pure helper and real encrypted repository path.