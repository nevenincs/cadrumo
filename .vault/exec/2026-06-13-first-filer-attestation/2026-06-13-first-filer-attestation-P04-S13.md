---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S13'
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

# Add a real-storage test proving the alta-containing period stays in scope as the first obligation and is NOT suppressed

## Scope

- `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`

## Description

- Add `test_alta_containing_period_stays_in_scope_as_first_obligation`: real-storage M390/2025 with `activity_start_date=2025-10-01` (first day of 4T) suppresses 1T/2T/3T but keeps 4T in scope as the first obligation.

## Outcome

- Landed in commit `0c69ec483`. Asserts 4T is NOT suppressed (`no_prior_obligation is None`), still demands its filing (`MISSING_CURRENT_FILING_RECORD`), and the suppressed set is exactly `{1T,2T,3T}`. Boundary pinned via `Period` authority.

## Notes

- Proves the ratified boundary: alta-CONTAINING period is the first obligation, only strictly-prior suppressed.
