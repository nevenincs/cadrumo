---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S12'
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

# Add a real-storage test proving an empty pre-activity span produces no cross-period blocker (absent-by-design) and verify completes on current-period merits for a genuine first filer

## Scope

- `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`

## Description

- Add `test_empty_pre_activity_span_produces_no_cross_period_blocker_for_genuine_first_filer`: real-storage M390/2025 with `activity_start_date=2026-01-01` suppresses all four 2025 M303 quarters; the verdict is fully clean with every dependency facet-stamped and no observation seeded.

## Outcome

- Landed in commit `0c69ec483`. Asserts `requires_clean_state` True, `clean` True, no blockers, all dependencies suppressed with `OPERATOR_DECLARED` provenance and the correct scoping date, and the suppression advisory rollup True. Passes under `isolated_runtime_profile`.

## Notes

- Real registry authority and real secure storage; no mocks/stubs/skips.
