---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S49'
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# Introduce typed live-auth acquisition outcomes for no-prompt, operator-timeout, QR-required, certificate-required, wrong-identity, AEAT-403, DOM-drift, and authenticated. Partial 2026-05-26: `LiveIvaAcquisitionFailureMode` and `classify_live_iva_acquisition_failure` now map Cl@ve and Sede adapter exceptions into application-level outcomes

## Scope

- `acquisition result wrapping and authenticated-success records remain open. Partial 2026-05-27: persisted Cl@ve session loading now accepts provider-specific encrypted metadata by narrowing it to provider-neutral identity`
- `provider kind`
- `authentication time`
- `and idle deadline before parsing`
- `these structural diagnostics must not be treated as operator-confirmed AEAT authentication. Completed 2026-05-27: `IvaRemoteStateAcquisitionReport` now carries a redacted auth outcome`
- `per-surface outcomes expose `outcome_mode`
- `auth failures propagate typed modes to both filed-history and wallet surfaces`
- `success records use `authenticated`
- `and certificate-required auth gates remain distinct from generic AEAT 403. Review follow-up 2026-05-27: legacy acquisition manifests that predate auth/outcome fields now validate with explicit legacy auth defaults instead of breaking profile reload`
- `src/aeat/adapters/outbound/aeat/auth src/aeat/application/auth src/aeat/application/live`

## Description

- Reconciled this historical checked plan row to a canonical per-step exec record.
- Verified the row remains checked in `2026-05-19-live-iva-compensation-wallet-plan` at HEAD.
- Preserved the plan row, source tree, and prior exec/audit artifacts unchanged.

## Outcome

`vaultspec-core vault add exec` created this record with a `step_id` matching the checked row. The implementation evidence is the current checked plan row plus the feature source, tests, and audits already referenced by that row and its scope; this pass repairs traceability for `plan-closure-requires-exec-records` only.

## Notes

No new code, live AEAT access, plan checkbox change, source kind, resolver convention, or validator convention was introduced. The standing open live verification row `W06.P15.S56` remains separate and is not closed by this reconciliation.
