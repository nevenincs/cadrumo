---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S17'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace first-filer-attestation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

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
