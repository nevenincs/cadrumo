---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S04'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---




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
