---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S08'
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

# Thread the declared activity_start_date parameter into evaluate_cross_period_clean_state and cross_period_dependency_requirements without letting callers pass an ad hoc dependency set, preserving registry-derived guard semantics

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Thread an optional `activity_start_date: date | None` parameter into `evaluate_cross_period_clean_state`; it partitions the registry-derived requirements, evaluates the in-scope set as before, and emits clean facet-stamped rows for the suppressed set.
- Callers pass the declared date, never an ad hoc dependency set, preserving the registry-derived guard semantics.

## Outcome

- Landed in commit `4026deb0d`. When `activity_start_date` is `None` every dependency is evaluated exactly as before. Verified by the 29 pre-existing clean-state tests staying green plus the 5 new P04 calculations-layer tests.

## Notes

- The registry-derived-graph constraint of `2026-06-05-cross-period-calculation-guards-adr` is preserved: the scoping is a filter over the derived requirements.
