---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
step_id: 'S12'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m303-form-vs-semantic-casilla-dual-keying with a kebab-case feature tag, e.g. #foo-bar.
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

# Flip box 45 (Total a deducir cuota) to computed with formula modelo-303-dr303-45-projection copying iva.cuota-deducible-total, carrying box 45 legal_refs

## Scope

- `ensure topological order computes iva.cuota-deducible-total before box 45`
- `and verify box 45 equals the total registry-authoritatively`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`

## Description

- Flip box 45 (deducible total (topological order computes the total first)) from input_kind manual to input_kind computed.
- Author single-leaf projection formula `modelo-303-dr303-45-projection` (target 45, expression the one casilla leaf `iva.cuota-deducible-total`, money-2 rounding) with box 45 legal_refs verbatim and a boe-modelo-303-2008-form source citation.
- Register the formula id in the revision formulas list.

## Outcome

- On a real ledger-fed calculate, box 45 equals its semantic source `iva.cuota-deducible-total` registry-authoritatively (asserted in test_calculate_projects_official_boxes_from_semantic_sources / test_pull_and_calculate_paths_produce_equal_projected_box_values).
- A caller can no longer override box 45 (computed-input rejected) — one aggregation path, pull == calculate by construction.

## Notes

- Projection formulas live in formulas/0001-dr303-projections.toml (directory-mode fragment) to keep revision.toml under the reviewability baseline.
