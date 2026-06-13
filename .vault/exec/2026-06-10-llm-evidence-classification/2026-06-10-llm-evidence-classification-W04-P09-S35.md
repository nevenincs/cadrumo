---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S35'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
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

# Roll classify --llm with a real cloud CLI (agy/codex) and --read-evidence --evidence-acknowledged

## Scope

- `confirm the model reads the invoice and the decision stamps llm provenance`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Run `app ledger classify <tx> --llm codex --saturate --read-evidence --evidence-acknowledged` against the real authenticated `codex` cloud CLI on the attached invoice.
- Re-run with `--apply` to persist the accepted suggestion.

## Outcome

- The model read the invoice (the bank row carried only "PAGO SUMINISTROS … 302.50"; the model returned base 250.00 / IVA 52.50, only knowable from the invoice) and classified BUSINESS / `hardware_amortizable`. `--apply` stamped `clasificado-por: llm:codex`, persisted the decision, set review status `reviewed`, and emitted a `ledger.transaction.classified` event. Provenance + evidence-read confirmed against the real model. Captured in audit `2026-06-13-llm-evidence-classification-audit`.

## Notes

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
