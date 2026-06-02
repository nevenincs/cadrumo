---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S199'
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

# delete duplicate AuthConfigureDanglingActiveProfileError registration

## Scope

- `the class is registered twice at lines 84-92 and 95-103`
- `src/aeat/core/errors/registry/_application.py`

## Description

Removed the duplicate `AuthConfigureDanglingActiveProfileError` registration in `src/aeat/core/errors/registry/_application.py` (the second of the two `REFUSED_AUTH_CONFIGURE_DANGLING_ACTIVE_PROFILE` ErrorCode entries). Co-landed with the S198 dedup since both lived in the same adjacent duplicate-pair block. Registry now has 106 unique declared codes.

## Outcome

Closed by direct code edit; see Description above.

## Notes

Real cleanup, not audit-based — duplicate registrations were live in the registry and the alias was unused.
