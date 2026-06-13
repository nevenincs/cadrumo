---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S10'
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

# Emit a non-blocking advisory verification finding when a suppression rests on an operator-declared-but-uncorroborated activity-start date, mirroring the existing unstamped-revision advisory severity that keeps the grant path open

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Emit `_cross_period_operator_declared_suppression_advisory_finding`: a non-blocking `ADVISORY` (`WARNING` severity) finding when a suppression rests on an operator-declared (uncorroborated) activity-start date, mirroring the existing unstamped-revision advisory severity that keeps the grant path open.

## Outcome

- Landed in commit `5d6549183`. The advisory names the modelo/year/period and the declared date and states it is not yet censo-corroborated. Proven by P04.S16 `test_verify_surfaces_operator_declared_suppression_advisory_without_blocking`.

## Notes

- WARNING severity keeps the grant path open per `_classify_verification_outcome`; the suppression is never presented as AEAT-authoritative.
