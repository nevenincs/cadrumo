---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S08'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Flip box 27 (Total cuota devengada) to computed with formula modelo-303-dr303-27-projection copying iva.cuota-devengada-total, carrying box 27 legal_refs

## Scope

- `ensure topological order computes iva.cuota-devengada-total before box 27`
- `and verify box 27 equals the total registry-authoritatively`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`

## Description

- Flip box 27 (devengado total (topological order computes the total first)) from input_kind manual to input_kind computed.
- Author single-leaf projection formula `modelo-303-dr303-27-projection` (target 27, expression the one casilla leaf `iva.cuota-devengada-total`, money-2 rounding) with box 27 legal_refs verbatim and a boe-modelo-303-2008-form source citation.
- Register the formula id in the revision formulas list.

## Outcome

- On a real ledger-fed calculate, box 27 equals its semantic source `iva.cuota-devengada-total` registry-authoritatively (asserted in test_calculate_projects_official_boxes_from_semantic_sources / test_pull_and_calculate_paths_produce_equal_projected_box_values).
- A caller can no longer override box 27 (computed-input rejected) — one aggregation path, pull == calculate by construction.

## Notes

- Projection formulas live in formulas/0001-dr303-projections.toml (directory-mode fragment) to keep revision.toml under the reviewability baseline.
