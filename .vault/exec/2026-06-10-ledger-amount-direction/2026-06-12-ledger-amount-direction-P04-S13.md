---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S13'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# CLI Amount Tests

## Scope

Step `P04.S13`.

## Description

- Added CLI integration coverage for negative `ledger add --amount`.
- Added acceptance coverage for non-negative outgoing `ledger add`.
- Added CLI integration coverage for negative `ledger update --amount`.

## Outcome

The CLI tests prove the operator sees the instructive magnitude-plus-direction refusal.

## Notes

The tests run through the real Typer application and profile/storage setup.
