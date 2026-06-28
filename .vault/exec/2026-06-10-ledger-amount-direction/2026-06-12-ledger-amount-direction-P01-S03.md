---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S03'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Split Child Magnitudes

## Scope

Step `P01.S03`.

## Description

- Removed split-child sign consistency semantics.
- Kept exact child-sum validation against the parent magnitude.
- Documented that split children inherit `parent.direction`.

## Outcome

Split children carry non-negative amounts and receive flow from the parent transaction direction.

## Notes

An additional evidence-split helper guard now rejects negative gross inputs instead of preserving sign.
