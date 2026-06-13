---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
step_id: 'S04'
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

# check git status for peer WIP on the M130 registry, then flip casilla 05 from input_kind manual to bound and add the previous_filing span binding selecting source_modelo 130 with the new expanding-span mode, carrying raw prior casilla 07 and casilla 16 anchors with aggregation op sum

## Scope

- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-bindings.toml`

## Description

- Checked git status; the M130 casilla-05 flip was already drafted (deferred P02) in the working tree. Verified it against the plan and ADR.
- Confirmed casilla 05 flips from `input_kind = "manual"` to `input_kind = "bound"` with `binding = "modelo-130-pagos-fraccionados-anteriores"`.
- Confirmed the binding selects `source_modelo = "130"`, `source_casillas = ["07", "16"]`, `prior_quarter_expanding_span = true`, `max_year_delta = 0`, consuming the P01 expanding-span anchor set with aggregation op `prior_pagos_fraccionados`.

## Outcome

Casilla 05 is a bound carry emitting the prior casilla 07 / 16 anchors per same-ejercicio prior quarter into the multi-anchor resolve path. Landed in commit `a67b77c87`.

## Notes

The deferred draft was correct; no correction needed.
