---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S45'
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# Add redacted live-auth preflight diagnostics for active profile identity, configured DNI/NIE presence, support-number presence, certificate provider state, Cl@ve preference, and timeout. Partial 2026-05-26: existing Cl@ve diagnostic payload fields for identity/config/certificate state are now exposed through the application diagnostic read model, including `prefer_non_qr` and `timeout_ms`

## Scope

- `CLI preflight rendering remains open. Completed 2026-05-27: `build_live_auth_preflight_report` now exposes a redacted application-owned preflight report`
- `and IVA live CLI pull/capture-history commands render provider`
- `active-profile`
- `identity-alignment`
- `route-mode`
- `timeout`
- `support-number presence`
- `certificate state`
- `and persisted-session presence to stderr before invoking live auth. Review follow-up 2026-05-27: the same preflight now runs before filed-history list/capture/capture-sources`
- `DEHu notifications capture`
- `and expedientes capture live-read entrypoints`
- `src/aeat/application/auth src/aeat/entrypoints/cli/_app_live.py`

## Description

- Reconciled this historical checked plan row to a canonical per-step exec record.
- Verified the row remains checked in `2026-05-19-live-iva-compensation-wallet-plan` at HEAD.
- Preserved the plan row, source tree, and prior exec/audit artifacts unchanged.

## Outcome

`vaultspec-core vault add exec` created this record with a `step_id` matching the checked row. The implementation evidence is the current checked plan row plus the feature source, tests, and audits already referenced by that row and its scope; this pass repairs traceability for `plan-closure-requires-exec-records` only.

## Notes

No new code, live AEAT access, plan checkbox change, source kind, resolver convention, or validator convention was introduced. The standing open live verification row `W06.P15.S56` remains separate and is not closed by this reconciliation.
