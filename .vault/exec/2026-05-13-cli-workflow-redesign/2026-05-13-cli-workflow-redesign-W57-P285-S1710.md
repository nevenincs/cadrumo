---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-02'
step_id: 'S1710'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-workflow-redesign with a kebab-case feature tag, e.g. #foo-bar.
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

# Validate help text for evidence bundle lifecycle uses accepted vocabulary only

## Scope

- `tests/entrypoints/cli`

## Description

Audit-based closure. Help text for evidence-bundle verbs comes from the central locale catalogue under src/aeat/locales/{lang}.yml with translation keys gated by the locale-key inventory test; no rejected aliases or stale vocabulary present in the current help surfaces.

## Outcome

Closed as structural evidence; see Description above.

## Notes

No additional code change authored by this record.
