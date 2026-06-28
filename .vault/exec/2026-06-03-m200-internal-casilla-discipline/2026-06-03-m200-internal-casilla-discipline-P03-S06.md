---
tags:
  - '#exec'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S06'
related:
  - "[[2026-06-03-m200-internal-casilla-discipline-plan]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
  - "[[2026-06-02-modelo-200-base-determination-adr]]"
---

# Flip internal_only=true on bin-aplicada-maxima casilla TOML

## Scope

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-bin-aplicada-maxima.toml`

## Description

Added `internal_only = true` between `formula = "modelo-200-2024-bin-aplicada-maxima"` and `legal_refs` on the `DP200014:bin-aplicada-maxima` casilla TOML. The casilla retains its existing `input_kind = "computed"`, empty `export_refs` (the field is absent, defaulting to `()`), formula grounding, and LIS art. 26 / art. 25 legal_refs — every condition the schema validator now enforces under `internal_only = true`.

## Outcome

The M200 BIN-compensation ceiling carries its intent at its TOML source. The schema's validator chain accepts it (COMPUTED + no exports + grounded). The `derive_calculation_completeness_casillas` exemption (P02.S04+P02.S05) routes around the Diseño-presence check for it.
