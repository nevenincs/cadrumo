---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:fa937a9b2e251e08dce8bdef72edd1b6295b9f506a061c8d6b3752b3b88325eb'
step_id: 'S61'
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# Add reload APIs that return latest and historical remote IVA evidence for a profile without requiring a live AEAT login. Completed 2026-05-27: `load_iva_remote_state` reloads stored filed-history state, carry-forward lots, authority decisions, and redacted wallet observation summaries from active-profile secure storage without live AEAT contact. Follow-up 2026-05-27: the same stored-evidence report now includes redacted acquisition-manifest summaries with hashed manifest refs and per-surface typed outcomes, so downstream reconciliation can inspect filed-history, wallet observations, authority decisions, and acquisition attempts through one profile-local backend view

## Scope

- `src/aeat/application/live src/aeat/application/calculations`

## Description

- Reconciled this historical checked plan row to a canonical per-step exec record.
- Verified the row remains checked in `2026-05-19-live-iva-compensation-wallet-plan` at HEAD.
- Preserved the plan row, source tree, and prior exec/audit artifacts unchanged.

## Outcome

`vaultspec-core vault add exec` created this record with a `step_id` matching the checked row. The implementation evidence is the current checked plan row plus the feature source, tests, and audits already referenced by that row and its scope; this pass repairs traceability for `plan-closure-requires-exec-records` only.

## Notes

No new code, live AEAT access, plan checkbox change, source kind, resolver convention, or validator convention was introduced. The standing open live verification row `W06.P15.S56` remains separate and is not closed by this reconciliation.
