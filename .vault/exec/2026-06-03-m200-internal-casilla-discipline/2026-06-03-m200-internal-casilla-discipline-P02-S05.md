---
tags:
  - '#exec'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S05'
related:
  - "[[2026-06-03-m200-internal-casilla-discipline-plan]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
---

# Short-circuit Diseño-presence check for internal_only pairs

## Scope

- `src/aeat/domain/calculations/registry/_record_design.py`

## Description

Inside the multi-segment branch of `derive_calculation_completeness_casillas`, immediately before the `if diseno_pairs is not None and segmento is not None and (segmento, number) not in diseno_pairs` check, added a clause that intercepts `(segmento, number) in internal_only_identities`. The intercept appends `DerivedDisenoCasilla(segmento=segmento, number=number)` and `continue`s — preserving the segment-carrying identity for downstream manifest consumers, skipping the Diseño-presence check. A comment in-place names the contract.

## Outcome

`DP200014:bin-aplicada-maxima` (the LIS art. 26.1 BIN-compensation ceiling) now passes through the derivation without triggering the Diseño-presence `RegistryValidationError`. The gate's discipline against wrong-segment mis-tags is unchanged for every non-internal_only casilla.
