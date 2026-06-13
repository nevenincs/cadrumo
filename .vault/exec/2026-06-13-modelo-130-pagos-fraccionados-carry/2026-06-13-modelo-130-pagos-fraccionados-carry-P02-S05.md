---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
step_id: 'S05'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-130-pagos-fraccionados-carry with a kebab-case feature tag, e.g. #foo-bar.
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

# author the casilla 05 registry formula computing sum of per-quarter max(0, prior 07_q) minus sum of prior 16_q (positive-part per quarter before summing, minoracion subtracted), preserving the carried prior-filing values unmodified (shape 2a)

## Scope

- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/formulas/0001-formulas.toml`

## Description

- Authored the casilla-05 computation as the `prior_pagos_fraccionados` aggregation op (landed in P01), encoding `Sum max(0, prior 07_q) - Sum prior 16_q` per the AEAT instrucciones rather than a separate registry formula.
- Confirmed the op applies the positive-part PER QUARTER before summing and subtracts the sum of prior casilla 16; carried prior-filing values are read unmodified (shape 2a).

## Outcome

Casilla 05 computes the instrucciones identity from the carried raw prior 07 / 16 anchors. The op (not a formula) is the canonical encoding; the registry test asserts the value against an independent identity. Landed in commit `a67b77c87`.

## Notes

The ADR shape-2a registry formula is realised as the P01 aggregation op, keeping carried evidence faithful to what was filed while putting the positive-part + minoración logic in one auditable op.
