---
tags:
  - '#plan'
  - '#aeat-grounding-completion'
date: '2026-06-14'
modified: '2026-06-29'
tier: L3
related:
  - '[[2026-06-14-aeat-grounding-completion-adr]]'
  - '[[2026-06-14-aeat-grounding-completion-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `aeat-grounding-completion` plan

## Wave `W01` - Módulos magnitude-exclusion limits

Author the estimación-objetiva (módulos) DT 32ª in-force exclusion magnitudes as grounded registry parameters and surface an advisory gate when a declared volume exceeds a limit. Closes audit finding V3, the former corpus-only módulos magnitude gap.

### Phase `W01.P01` - Author módulos exclusion magnitudes

Author the four DT 32ª in-force módulos exclusion magnitudes as grounded registry parameters.

- [x] `W01.P01.S01` - Author módulos exclusion magnitudes as registry parameters: 250.000 EUR general rendimientos, 125.000 EUR operaciones con obligación de factura, 250.000 EUR agrícolas/ganaderas/forestales, 250.000 EUR volumen de compras - grounded ley-35-2006:art-31 + dt-32 + Orden de módulos; `src/aeat/_data/registry/aeat/`.

### Phase `W01.P02` - Advisory exclusion gate

Surface a Notice when a declared estimación-objetiva volume exceeds an exclusion magnitude.

- [x] `W01.P02.S02` - Add an advisory exclusion gate emitting a Notice when a declared estimación-objetiva volume exceeds an authored magnitude (advisory-first); `src/aeat/application/`.

## Wave `W02` - IS rate-surface gaps

Build the IS rate-surface gaps the verification swarm found. The true Entidad de Reducida Dimensión (INCN<10M, LIS art.101) DT 44ª transitional schedule is now carried as its own grounded registry lane, and the deferred bracket-based casilla-00558 rate echo is closed in the current registry, so the displayed micro-empresa rate reflects the two-tranche scale for 2025/2026 instead of the stale flat 23%. Closes audit finding V1 (cuota already correct; echo stale).

### Phase `W02.P03` - ERD INCN<10M art.101 schedule

Author the true ERD (INCN<10M) DT 44ª transitional rate schedule.

- [x] `W02.P03.S03` - Author the ERD INCN<10M (LIS art.101) DT 44ª schedule as registry parameters distinct from the micro-empresa scalar, grounded on ley-27-2014:art-101 and ley-27-2014:dt-44; `src/aeat/_data/registry/aeat/modelos/200/`.

### Phase `W02.P04` - M200 casilla 00558 two-tranche rate echo

Land the deferred bracket-based rate echo for the two-tranche micro-empresa rate.

- [x] `W02.P04.S04` - Land the deferred bracket-based casilla-00558 rate echo so the displayed micro-empresa rate reflects the two-tranche scale for 2025/2026; `src/aeat/_data/registry/aeat/modelos/200/`.

## Description

## Steps

## Parallelization

## Verification

- 2026-06-29 current-state check for `W01.P02.S02`: the advisory consumer lives in
  `src/aeat/application/modelo/_objective_estimation_advisory.py`, reads the
  four declared objective-estimation prior-year volume fields from
  `TaxpayerProfile`, emits advisory warnings for Modelo 100/131 within the
  2016-2026 scope, and carries legal/source refs from the grounded parameters.
  Verified in the focused run that included
  `test_objective_estimation_exclusion_advisory.py`.
- 2026-06-29 current-state check for `W02.P03.S03`: the Modelo 200 registry
  declares `is.modelo-200.tipo-gravamen-erd-art101` and
  `is.modelo-200.cuota-integra-bracket-erd-art101`, with formulas routing
  Art.101 general-rate entity forms to those parameters and the completeness
  manifest carrying `ley-27-2014:art-101` and `ley-27-2014:dt-44`.
  Verified with `test_modelo_200_tipo_gravamen_dispatch.py` and
  `test_modelo_200_cuota_integra_lanes.py`.
- 2026-06-29 current-state check for `W02.P04.S04`: the Modelo 200 registry
  contains `is.modelo-200.tipo-gravamen-pyme-display` with dated display
  rates 23/21/19 for 2024/2025/2026; `DP200014:00558` routes
  micro-empresa general forms to that scalar echo; `DP200014:00562` remains
  bracket-derived. Verified with
  `test_modelo_200_tipo_gravamen_dispatch.py` (18 passed),
  `test_modelo_200_cuota_integra_lanes.py` (14 passed), and
  `test_modelo_200_temporal_coverage.py` (7 passed).
- 2026-06-29 no-legacy check: the old `uses_objective_estimation_irpf` input
  surface is retired. Setup, profile projection, applicability, and Modelo 131
  deadline-window routing now use `irpf.estimation_regime`; tests retain only
  negative assertions that the legacy field is rejected or absent.
