---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S08'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Import Contract Tests

## Scope

Step `P02.S08`.

## Description

- Added import coverage for zero-amount refusal.
- Added coverage for outgoing magnitude storage with `OUTGOING`.
- Added coverage for magnitude storage with `INTERNAL_TRANSFER`.

## Outcome

The application import tests pin the parse-boundary direction contract.

## Notes

Provider tests also assert parsed raw amounts are non-negative.
