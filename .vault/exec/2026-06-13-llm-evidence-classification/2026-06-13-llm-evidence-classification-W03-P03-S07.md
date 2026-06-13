---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
step_id: 'S07'
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

# Adversarially test evidence parsing (text-layer, in-memory rasterise, vision dispatch) against the corpus

## Scope

- `src/aeat/application/ledger/tests/test_evidence_corpus_parsing.py`

## Description

- Adversarially test evidence parsing (text-layer extraction, scan-only -> rasterise fallback, image load, malformed/empty raise) against the corpus.

## Outcome

- 8 corpus-parsing tests pass; parsers raise (never crash) on hostile input. Committed `1572036a8`.

## Notes

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
