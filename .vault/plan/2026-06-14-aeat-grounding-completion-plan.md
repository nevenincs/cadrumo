---
tags:
  - '#plan'
  - '#aeat-grounding-completion'
date: '2026-06-14'
modified: '2026-06-15'
tier: L3
related:
  - '[[2026-06-14-aeat-grounding-completion-adr]]'
  - '[[2026-06-14-aeat-grounding-completion-research]]'
---
# `aeat-grounding-completion` plan

## Wave `W01` - Módulos magnitude-exclusion limits

Author the estimación-objetiva (módulos) DT 32ª in-force exclusion magnitudes as grounded registry parameters and surface an advisory gate when a declared volume exceeds a limit. Closes audit finding V3 (the limits exist only in corpus text, never as enforceable values).


### Phase `W01.P01` - Author módulos exclusion magnitudes

Author the four DT 32ª in-force módulos exclusion magnitudes as grounded registry parameters.

- [x] `W01.P01.S01` - Author módulos exclusion magnitudes as registry parameters: 250.000 EUR general rendimientos, 125.000 EUR operaciones con obligación de factura, 250.000 EUR agrícolas/ganaderas/forestales, 250.000 EUR volumen de compras — grounded ley-35-2006:art-31 + dt-32 + Orden de módulos; `src/aeat/_data/registry/aeat/`.

### Phase `W01.P02` - Advisory exclusion gate

Surface a Notice when a declared estimación-objetiva volume exceeds an exclusion magnitude.

- [ ] `W01.P02.S02` - Add an advisory exclusion gate emitting a Notice when a declared estimación-objetiva volume exceeds an authored magnitude (advisory-first); `real-behavior test; `src/aeat/application/`.

## Wave `W02` - IS rate-surface gaps

Build the two IS gaps the verification swarm found: the true Entidad de Reducida Dimensión (INCN<10M, LIS art.101) DT 44ª transitional schedule (24/23/22/21), and the deferred bracket-based casilla-00558 rate echo so the displayed micro-empresa rate reflects the two-tranche scale for 2025/2026 instead of the stale flat 23%. Closes audit finding V1 (cuota already correct; echo stale).

### Phase `W02.P03` - ERD INCN<10M art.101 schedule

Author the true ERD (INCN<10M) DT 44ª transitional rate schedule.

- [ ] `W02.P03.S03` - Author the ERD INCN<10M (LIS art.101) DT 44ª schedule 24/23/22/21 (2025-2028) as a registry parameter distinct from the micro-empresa scalar; `grounded ley-27-2014:art-101 + dt-44; `src/aeat/_data/registry/aeat/modelos/200/`.

### Phase `W02.P04` - M200 casilla 00558 two-tranche rate echo

Land the deferred bracket-based rate echo for the two-tranche micro-empresa rate.

- [ ] `W02.P04.S04` - Land the deferred bracket-based casilla-00558 rate echo so the displayed micro-empresa rate reflects the two-tranche scale for 2025/2026; `prove the cuota is unchanged; `src/aeat/_data/registry/aeat/modelos/200/`.

## Description


## Steps







## Parallelization


## Verification

