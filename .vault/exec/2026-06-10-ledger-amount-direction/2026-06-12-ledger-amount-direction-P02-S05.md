---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:b3f1d1ab6ec2475927ea008abe961a7e7bbcb1182c486d4cf473e4b8f79fbf3e'
step_id: 'S05'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Import Direction Threading

## Scope

Step `P02.S05`.

## Description

- Removed downstream `_direction_from_amount` usage.
- Threaded parser-supplied `ParsedLedgerRow.direction` through dry-run and persisting import evaluation.
- Kept `value_in_eur` as an absolute EUR magnitude.

## Outcome

Import consumers no longer infer direction from stored amount sign.

## Notes

Source sign handling remains only at the inbound provider parse boundary.
