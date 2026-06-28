---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S04'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Flip box 06 (RG 10pct cuota) to computed with formula modelo-303-dr303-06-projection copying iva.repercutido.reducido, carrying box 06 legal_refs

## Scope

- `verify box 06 equals iva.repercutido.reducido on calculate and via pull (one-aggregation-path parity)`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`

## Description

- Flip box 06 (devengado RG 10pct) from input_kind manual to input_kind computed.
- Author single-leaf projection formula `modelo-303-dr303-06-projection` (target 06, expression the one casilla leaf `iva.repercutido.reducido`, money-2 rounding) with box 06 legal_refs verbatim and a boe-modelo-303-2008-form source citation.
- Register the formula id in the revision formulas list.

## Outcome

- On a real ledger-fed calculate, box 06 equals its semantic source `iva.repercutido.reducido` registry-authoritatively (asserted in test_calculate_projects_official_boxes_from_semantic_sources / test_pull_and_calculate_paths_produce_equal_projected_box_values).
- A caller can no longer override box 06 (computed-input rejected) — one aggregation path, pull == calculate by construction.

## Notes

- Projection formulas live in formulas/0001-dr303-projections.toml (directory-mode fragment) to keep revision.toml under the reviewability baseline.
