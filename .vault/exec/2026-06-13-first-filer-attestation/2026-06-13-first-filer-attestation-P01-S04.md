---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S04'
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

# Add the pure period-strictly-before-activity-start predicate over a declared date routed through Period boundary authority, unit-testing that the alta-containing period is NOT before-start

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add the pure `_period_strictly_before_activity_start(period, activity_start_date)` predicate routed through `Period` boundary authority (`Period.end_date`, `Period.has_date_span`).
- Mirror the deadline engine pre-start gate: a period is strictly-prior only when its entire inclusive span ends before the activity-start date, so the alta-containing period stays in scope.

## Outcome

- Landed in commit `4026deb0d`. Boundary semantics verified directly: 1T ends 2025-03-31 and is strictly before a 2025-07-01 alta (True); the alta-containing 3T returns False; a non-calendar clave returns False. Proven by P04.S13 and the P04 non-calendar test.

## Notes

- Routed through the single `Period` boundary authority per `period-filter-single-boundary-authority`; no parallel inclusion math.
