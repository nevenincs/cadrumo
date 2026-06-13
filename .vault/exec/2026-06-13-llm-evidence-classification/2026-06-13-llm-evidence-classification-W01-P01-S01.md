---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
step_id: 'S01'
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

# Thread provider Optional with lazy text-classifier resolution in suggest/saturate/split classification

## Scope

- `src/aeat/application/ledger/_llm_classification.py`

## Description

- Thread `provider` Optional through suggest/saturate/split with lazy text-classifier resolution; the dispatch helpers raise an instructive `TransactionValidationError` when the text path needs a provider and none was supplied. Suggestion `provider` fields made Optional with guarded `.value` reads.

## Outcome

- Image evidence now classifies on-host with no `--llm`; the text/cloud path still requires a provider. Committed `41c17af16`.

## Notes

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
