---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S06'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Import Zero Amount Refusal

## Scope

Step `P02.S06`.

## Description

- Added provider-boundary zero-amount refusal in `build_raw_transaction`.
- Routed provider failures through the ledger import validation error envelope.

## Outcome

A zero-value source movement is refused before import classification can silently treat it as incoming.

## Notes

The focused import test asserts the translated ledger-import failure and the zero-amount reason.
