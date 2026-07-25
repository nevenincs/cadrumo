---
tags:
  - '#exec'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S07'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-plan]]"
---

# Report as a finding any synthetic M303 expectation that stays green through this layout change, because a green expectation across a layout change is itself evidence the corpus is not measuring layout, rather than quietly leaving it alone

## Scope

- `.vault/audit/`
- `synthetic M303 expectations`

## Description

- Enumerate every synthetic M303 expectation and classify it as would-break or would-stay-green.
- Persist the findings as a vault audit document.

## Outcome

All 76 expected-value entries stay green and none reference a dropped id, confirmed by independent literal-string measurement rather than inherited from the companion audit. The audit records this as the central finding, with the empirical corollary that all 15 synthetic fixtures score exactly 1.0 coverage against the post-change profiles, so the corpus cannot validate the coverage floor at any value.

Five further findings are recorded: the coverage floor's zero headroom at the worst quarter; the parse path no longer exercising the engine; the misnamed real-copy constant; the annex sidecar prose mismatch; and the Modelo 130 fixture's undeclared provenance.

## Notes

One correction to the companion audit is recorded as its own finding. That audit scoped the annex sidecar prose defect to a single file; re-measured, the mismatched clause appears in all five sidecars in the annex directory.

Both honesty repairs the companion audit recommended were applied. The constant named for a real redacted Modelo 303 declaration resolved to a fixture whose sidecar declares synthetic provenance; it and its test are renamed with the reason recorded at the definition site. Checked as a class, the analogous Modelo 190 constant is correctly named against a real-corpus sidecar, so the misnaming was isolated.
