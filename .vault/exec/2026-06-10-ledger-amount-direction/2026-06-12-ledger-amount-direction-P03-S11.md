---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:20cd7b5e80de4bfed20195b86bfeedfad175fa88f39ca1c71f4557fc75198b0a'
step_id: 'S11'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Evidence Anti-Tautology Proof

## Scope

Step `P03.S11`.

## Description

- Added a persisted evidence-payload mutation that rewrites `amount` negative.
- Asserted load-time `ValidationError` when the encrypted calculation revision catalogue is rehydrated.

## Outcome

The evidence-row non-negative gate is exercised at the persistence boundary.

## Notes

The test mutates the real encrypted-storage payload; it does not patch model behavior.
