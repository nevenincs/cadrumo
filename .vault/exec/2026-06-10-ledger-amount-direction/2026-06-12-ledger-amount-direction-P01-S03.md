---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:9d3dfc20c59151624acc46361d2ad47f53f0c6ad13a0de15fa0a8967f18136cb'
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
