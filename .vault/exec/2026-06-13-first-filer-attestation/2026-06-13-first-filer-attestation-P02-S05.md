---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S05'
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

# Apply the activity-start scoping filter to previous_filing-origin requirements in cross_period_dependency_requirements so a period strictly before the declared alta is dropped from the derived graph

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add `partition_cross_period_requirements_by_activity_start`, the application-layer filter that splits the registry-derived requirements into in-scope vs. strictly-pre-activity-suppressed using the P01.S04 predicate.
- Previous_filing-origin requirements whose period is strictly before the declared alta are dropped from the evaluated graph.

## Outcome

- Landed in commit `4026deb0d`. The partition is origin-agnostic; previous_filing-origin pre-activity anchors are suppressed. Proven by the P04.S14 uniformity test over M303/4T (previous_filing origin).

## Notes

- The registry stays pure: the filter operates over the derived requirements, the declared date is a grounded input, not a per-call ad hoc shrink.
