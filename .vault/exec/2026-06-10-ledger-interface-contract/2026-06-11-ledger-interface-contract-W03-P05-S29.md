---
tags: ['#exec', '#ledger-interface-contract']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S29'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# W03.P05.S29 Ratios Validate Findings Typed

Scope: close the ratios validate finding typing remainder.

## Description

- Add `RatiosValidateFindingPayload`.
- Change `RatiosValidateResult.findings` to typed finding rows.
- Add constructor coverage for validate findings.

## Outcome

`ledger ratios validate` findings now validate as strict nested output schemas. The ratios CLI tests passed in the widened ledger gate.

## Notes

No skipped work.
