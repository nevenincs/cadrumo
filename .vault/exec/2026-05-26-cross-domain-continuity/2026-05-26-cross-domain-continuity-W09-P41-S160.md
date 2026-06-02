---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S160'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
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

# delete address_postcode field from SetupAnswers or wire to real consumer recommend delete

## Scope

- `src/aeat/application/wizard/_setup_answers.py`

## Description

Deleted the `address_postcode: str = ""` field from `SetupAnswers`
in `src/aeat/core/profile.py:198`. The plan Step's path
(`application/wizard/_setup_answers.py:41`) is stale — the actual
field lives in `core/profile.py`. Grep across `src/` confirms zero
non-declaration references; the field was collected by the wizard
but never consumed downstream (per the originating
`2026-05-26-cross-domain-continuity-audit` Cluster L finding).

## Outcome

Real deletion. 29 tests across `core/test_profile.py` (12) and
`application/wizard/test_setup_answers.py` (17) continue to pass.
No callers existed to update.

## Notes

Plan's stated path is stale (refers to a `_setup_answers.py` that
does not exist under `application/wizard/`); the live home for the
field was `core.profile.SetupAnswers`. Plan-identifier preserved
for stability.
