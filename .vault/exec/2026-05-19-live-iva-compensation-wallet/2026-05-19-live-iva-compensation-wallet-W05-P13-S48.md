---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:5cb37404bc7e31f7df75687c1ff984410632fa69f6435bb1bf629645789d2356'
step_id: 'S48'
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# Add real-behavior diagnostic tests that use production auth diagnostics and redaction logic without private taxpayer fixtures, fakes, stubs, or monkeypatched browser behavior. Partial 2026-05-26: `src/aeat/application/auth/test_diagnostics.py` now drives the real secure-object diagnostic read model with sanitized payloads and centralized AEAT route constants

## Scope

- `live-driver regression coverage remains open. Completed 2026-05-27: the real `ClaveMovilAuthProvider` attempt-context path is exercised against active profile secure storage and sanitized Cl@ve settings`
- `proving route/mode/profile/support diagnostics are present while raw DNI/NIE and support values are absent. Review follow-up 2026-05-27: active profile identifiers and labels are now emitted only as redacted references/presence booleans in Cl@ve diagnostics`
- `and an accidental secure-storage plan/audit inclusion was removed by a dedicated repair commit`
- `src/aeat/application/auth src/aeat/adapters/outbound/aeat/auth`

## Description

- Reconciled this historical checked plan row to a canonical per-step exec record.
- Verified the row remains checked in `2026-05-19-live-iva-compensation-wallet-plan` at HEAD.
- Preserved the plan row, source tree, and prior exec/audit artifacts unchanged.

## Outcome

`vaultspec-core vault add exec` created this record with a `step_id` matching the checked row. The implementation evidence is the current checked plan row plus the feature source, tests, and audits already referenced by that row and its scope; this pass repairs traceability for `plan-closure-requires-exec-records` only.

## Notes

No new code, live AEAT access, plan checkbox change, source kind, resolver convention, or validator convention was introduced. The standing open live verification row `W06.P15.S56` remains separate and is not closed by this reconciliation.
