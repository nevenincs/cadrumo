---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S198'
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

# delete duplicate AuthProviderReservedError registration

## Scope

- `the class is registered twice at lines 62-65 and 106-109`
- `src/aeat/core/errors/registry/_application.py`

## Description

Removed the duplicate `AuthProviderReservedError` registration in `src/aeat/core/errors/registry/_application.py` (the second of the two `REFUSED_AUTH_PROVIDER_RESERVED` ErrorCode entries). The registry now has 106 unique declared codes, zero duplicates (verified by Counter on the tuple-key list). The 33 error-registry tests under `src/aeat/core/errors/` continue to pass.

## Outcome

Closed by direct code edit; see Description above.

## Notes

Real cleanup, not audit-based — duplicate registrations were live in the registry and the alias was unused.
