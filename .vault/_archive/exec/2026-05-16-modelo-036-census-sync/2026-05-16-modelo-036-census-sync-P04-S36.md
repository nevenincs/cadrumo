---
tags:
  - '#exec'
  - '#modelo-036-census-sync'
date: '2026-06-02'
step_id: 'S36'
related:
  - "[[2026-05-16-modelo-036-census-sync-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-036-census-sync with a kebab-case feature tag, e.g. #foo-bar.
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

# register every new error in the application error registry

## Scope

- `src/aeat/core/errors/registry/_application.py`

## Description

Closed as already-shipped under the Spanish-stem naming convention recorded in the sibling ADR `2026-06-02-modelo-036-census-sync-adr`. The plan was authored in English (`census*` / `_census.py` / `CensusSnapshot*`) before the codebase's `iva` / `renta` / `casilla` / `modelo` / `censo` Spanish-stem convention was applied to this surface. Implementation lives under the Spanish name (`censo*` / `_censo.py` / `Censo*`) and is verified by passing real-behavior tests and direct module inspection.

## Outcome

Audit-based closure. No new code authored by this record — the implementation predates this plan-row closure.

## Notes

Plan-identifier preserved verbatim per the plan-hardening convention. The Spanish-naming resolution is recorded in the sibling ADR for traceability.
