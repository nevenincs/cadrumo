---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-06-02'
step_id: 'S802'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace codebase-solidification with a kebab-case feature tag, e.g. #foo-bar.
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

# Introduce OutputLanguage StrEnum with members ES, EN, CA, HU at canonical home `src/aeat/core/external_constants.py`. Rebase SUPPORTED_OUTPUT_LANGUAGES to frozenset of OutputLanguage

## Scope

- `DEFAULT_OUTPUT_LANGUAGE to OutputLanguage.ES. Sweep ~200 consumer sites`
- `skip locale yml and normative-corpus json (data`
- `not control flow). One atomic commit. Tag relocation:OutputLanguage`
- `src/aeat/core/external_constants.py`

## Description

<!-- Succint line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Notes

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
