---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:10df90e6990105f29b14948bb1c4e863aa039db2e7df46de849d77d73aeec630'
step_id: 'S04'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Transaction Roundtrip Proof

## Scope

Step `P01.S04`.

## Description

- Added encrypted catalogue roundtrip coverage for non-negative amount plus direction.
- Added a persisted-payload corruption proof that rewrites a stored amount negative and asserts load refusal.

## Outcome

The storage boundary proves both the happy path and the anti-tautology negative-load refusal.

## Notes

The repository wraps the underlying validation error in stored-data drift handling.
