---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
step_id: 'S05'
related:
  - "[[2026-06-13-llm-evidence-classification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace llm-evidence-classification with a kebab-case feature tag, e.g. #foo-bar.
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

# Write a provenance sidecar per corpus fixture declaring real_corpus or synthetic_generated and its source

## Scope

- `src/aeat/application/ledger/tests/_evidence_corpus/`

## Description

- Write a provenance sidecar per fixture declaring `real_corpus` (source URL + licence) or `synthetic_generated`.

## Outcome

- Every fixture carries a `.provenance.json` sidecar; a gate asserts it. Committed `1572036a8`.

## Notes

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
