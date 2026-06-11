---
tags: ['#exec', '#ledger-interface-contract']
date: '2026-06-11'
step_id: 'S25'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# W03.P05.S25 Ratios Eligible Rows Typed

Scope: close the ratios eligible row typing remainder.

## Description

- Add `RatiosEligibleRowPayload`.
- Change `RatiosEligibleResult.rows` to a list of typed rows.
- Add constructor coverage for the eligible-row nested model.

## Outcome

`ledger ratios eligible` now has a strict nested row schema. The ratios CLI tests passed in the widened ledger gate.

## Notes

No emit-site rewrite was required because the existing production payload already matched the new typed model.
