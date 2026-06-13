---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
step_id: 'S36'
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

# Roll classify --llm --saturate against a real cloud CLI

## Scope

- `confirm the model selects the IVA category`
- `the system derives rate/base/amount`
- `and the printed-vs-derived advisory behaves`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Run `app ledger classify <tx> --llm codex --saturate --read-evidence --evidence-acknowledged` and inspect the saturated preview, then `--apply`.

## Outcome

- The model selected IVA category `domestic_general_21`; the system DERIVED base 250.00, rate 0.21, IVA 52.50 (250.00 = 302.50 / 1.21 — registry-grounded, not model-emitted). The persisted transaction carries the derived regulated fields and `llm:codex` provenance. The printed-vs-derived figures agreed, so no advisory fired (expected — the invoice IVA matched the derived IVA). Captured in audit `2026-06-13-llm-evidence-classification-audit`.

## Notes

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
