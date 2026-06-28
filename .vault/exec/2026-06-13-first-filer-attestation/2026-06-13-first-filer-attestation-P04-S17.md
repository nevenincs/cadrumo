---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S17'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Add a regression asserting no_prior_obligation provenance never enters _OFFICIAL_SOURCE_KINDS and the first local filing still persists under the non-official app_filing source kind

## Scope

- `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`

## Description

- Add `test_no_prior_obligation_provenance_never_enters_official_source_kinds`: asserts every `NoPriorObligationProvenanceKind` value is absent from `_OFFICIAL_SOURCE_KINDS` and that the official set is unchanged.
- Add `test_first_local_filing_still_persists_under_non_official_app_filing`: asserts `APP_FILING_SOURCE_KIND == "app_filing"` and is non-official.

## Outcome

- Landed in commit `0c69ec483`. The honesty regression locks the invariant that pre-activity suppression provenance can never masquerade as official AEAT evidence, and the first local filing stays non-official `app_filing`.

## Notes

- `_OFFICIAL_SOURCE_KINDS` and the `app_filing` kind are untouched, satisfying `local-filed-observations-are-non-official-evidence`.
