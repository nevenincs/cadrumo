---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
step_id: 'S04'
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

# Source licence-clean text-layer PDF, scanned/image PDF, and image invoices into a fixtures corpus

## Scope

- `src/aeat/application/ledger/tests/_evidence_corpus/`

## Description

- Source two Wikimedia Commons public-domain invoice images and an Apache-2.0 ZUGFeRD EN16931 reference invoice PDF (text layer); derive a real-content image-only scanned PDF.

## Outcome

- Four real_corpus fixtures sourced online into the corpus dir. Committed `1572036a8`.

## Notes

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
