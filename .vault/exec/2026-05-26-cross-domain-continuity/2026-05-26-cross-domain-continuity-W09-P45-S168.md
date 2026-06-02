---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S168'
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

# extract _covered_by_namespace to one location and import from the other

## Scope

- `src/aeat/locales/`

## Description

`_covered_by_namespace` was duplicated in both
`src/aeat/locales/cli.py` (line 112) and
`src/aeat/locales/manager.py` (line 426) with identical bodies.
Deleted the cli.py copy; added it to the cli.py import line from
manager.

## Outcome

Real refactor. 27 locale tests
(test_cli.py 9 + test_locale_translation_honesty.py 2 +
test_parity.py 16) pass after the dedup.

## Notes

manager.py copy was kept as the canonical because it carries the
docstring; cli.py copy was a bare-body duplicate.
