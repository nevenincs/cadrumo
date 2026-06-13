---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
step_id: 'S02'
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

# Route --read-evidence into the LLM path when --llm is absent

## Scope

- `refuse instructively when the text path needs a provider`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Route `--read-evidence` into the LLM path when `--llm` is absent; skip the provider-availability check when no provider is named.

## Outcome

- `classify --read-evidence` on a scanned/image invoice works with no provider; ty + 320 ledger tests green. Committed `41c17af16`.

## Notes

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
