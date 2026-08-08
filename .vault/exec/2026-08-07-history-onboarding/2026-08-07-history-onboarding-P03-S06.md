---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:cac1c2158db9c56c9d1bcc6f164f3ea196b1a57f820350b48bb5a718ce9fadc1'
step_id: 'S06'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add the FiledHistoryOnboardingResult typed result model carrying per-pair outcomes, IVA wallet reconciliation status, notificaciones pull status, the divergence Notice list, the CoverageScopingSignal classification and a prose denominator_note field, and no numeric completeness percentage or fraction over AEAT_REGISTER_OPTIONS-tagged pairs, verified by a strict roundtrip test plus a test asserting the model schema carries no percentage or fraction field

## Scope

- `src/cadrumo/entrypoints/cli/_app_live_payloads.py`

## Description

- Add `FiledHistoryOnboardingResult` and `FiledHistoryPairOutcomePayload` registered payloads.
- Add the strict roundtrip, the no-ratio gates and the refusal-versus-empty gates.

## Outcome

The payload carries NO completeness percentage and no fraction, and a gate keeps
it that way. A ratio over the walked pairs would have a denominator partly
supplied by AEAT's offered option list, whose scoping to this NIF is unconfirmed,
so the figure would read as coverage while its denominator may have nothing to do
with the taxpayer. A prose `denominator_note` states what was actually measured —
the honest form of the same information.

The per-pair payload keeps a REFUSAL separate from a legitimate zero. The walker
refuses a page whose grid declares more records than it rendered, so a refused
pair also reports zero rows; folding the two together would render a parse refusal
as "no filings found".

## Verification

uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py -q -n0
    12 passed in 5.89s

The no-ratio gate checks the field TYPES as well as the names, because a name
check alone would miss `coverage: float`. The refusal gate asserts both rows carry
`row_count == 0` first, so it proves the two are indistinguishable by row count
and therefore that the separate field is doing the work.

## Notes

The plan row named the classification field's type `CoverageScopingSignal`. The
shipped enum is `RegisterScopingSignal`, landed by `P01.S20`, and the payload
carries its value rather than introducing a second enum — a same-concept duplicate
would be exactly the fragmentation the discovery mandate exists to prevent. The
naming difference is in the row, not in the code.
