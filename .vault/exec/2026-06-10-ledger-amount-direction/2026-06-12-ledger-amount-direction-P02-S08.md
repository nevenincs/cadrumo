---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:62b92cd00e28a77e85ac570a3eb23ecb2bd558b9a4d48644a7f27da07a0ccf70'
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
