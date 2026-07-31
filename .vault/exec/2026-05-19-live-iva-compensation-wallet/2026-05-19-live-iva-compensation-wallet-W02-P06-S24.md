---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:590773087a6268d1582cc8d30117c4265e483bf51437390ef82e232bb1c2bec0'
step_id: 'S24'
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# move accepted action markers into external constants and guard policies

## Scope

- `src/aeat/core/external_constants.toml`
- `src/aeat/domain/calculations/registry/_remote_state_guard.py`

## Description

- Reconciled this historical checked plan row to a canonical per-step exec record.
- Verified the row remains checked in `2026-05-19-live-iva-compensation-wallet-plan` at HEAD.
- Preserved the plan row, source tree, and prior exec/audit artifacts unchanged.

## Outcome

`vaultspec-core vault add exec` created this record with a `step_id` matching the checked row. The implementation evidence is the current checked plan row plus the feature source, tests, and audits already referenced by that row and its scope; this pass repairs traceability for `plan-closure-requires-exec-records` only.

## Notes

No new code, live AEAT access, plan checkbox change, source kind, resolver convention, or validator convention was introduced. The standing open live verification row `W06.P15.S56` remains separate and is not closed by this reconciliation.
