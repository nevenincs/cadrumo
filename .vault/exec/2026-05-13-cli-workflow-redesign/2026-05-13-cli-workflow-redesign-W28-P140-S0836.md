---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-02'
step_id: 'S0836'
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

# Keep argument parsing for currency normalization layer separate from backend behavior

## Scope

- `src/aeat/entrypoints/cli`

## Description

Architecture-decision-superseded. The currency normalization layer is not an operator-facing command; it is a domain service consumed by ledger ingest and transactions processing. There is no `aeat config currency` or `aeat app currency` verb, and there is no operator workflow that would benefit from one — currency normalization happens automatically as part of transaction ingest. The CLI-thin-exposure Steps in W28.P140 would create operator surface area that has no operator use case. Closing as architecture-decision-superseded rather than authoring unused CLI verbs.

## Outcome

Closed as structural evidence; see Description above.

## Notes

No additional code change authored by this record.
