---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:2b8c09f6216278e297ad624e4a41a6bfd88d684034d2a31331691b1724b60953'
step_id: 'S06'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace history-onboarding with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-08-07-history-onboarding-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The add the FiledHistoryOnboardingResult typed result model carrying per-pair outcomes, IVA wallet reconciliation status, notificaciones pull status, the divergence Notice list, the CoverageScopingSignal classification and a prose denominator_note field, and no numeric completeness percentage or fraction over AEAT_REGISTER_OPTIONS-tagged pairs, verified by a strict roundtrip test plus a test asserting the model schema carries no percentage or fraction field and ## Scope

- `src/cadrumo/entrypoints/cli/_app_live_payloads.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
