---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S07'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Flip box 13 (otras ops inversion sujeto pasivo excl intracom cuota) to computed with formula modelo-303-dr303-13-projection copying iva.autorepercutido.interior.devengado (oficial casilla 13), carrying box 13 legal_refs

## Scope

- `verify box 13 equals that source`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`

## Description

- Flip box 13 (otras inversion sujeto pasivo devengado (oficial 13)) from input_kind manual to input_kind computed.
- Author single-leaf projection formula `modelo-303-dr303-13-projection` (target 13, expression the one casilla leaf `iva.autorepercutido.interior.devengado`, money-2 rounding) with box 13 legal_refs verbatim and a boe-modelo-303-2008-form source citation.
- Register the formula id in the revision formulas list.

## Outcome

- On a real ledger-fed calculate, box 13 equals its semantic source `iva.autorepercutido.interior.devengado` registry-authoritatively (asserted in test_calculate_projects_official_boxes_from_semantic_sources / test_pull_and_calculate_paths_produce_equal_projected_box_values).
- A caller can no longer override box 13 (computed-input rejected) — one aggregation path, pull == calculate by construction.

## Notes

- Projection formulas live in formulas/0001-dr303-projections.toml (directory-mode fragment) to keep revision.toml under the reviewability baseline.
