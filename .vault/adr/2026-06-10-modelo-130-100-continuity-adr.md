---
tags:
  - '#adr'
  - '#modelo-130-100-continuity'
date: '2026-06-10'
modified: '2026-10-03'
body_hash: 'sha256:19086e8d3a45ce9d4b0568a4ae31828fc3f413244ba06c5db5b2070a8d2d53b1'
related:
  - '[[2026-06-10-modelo-130-100-continuity-research]]'
---

# `modelo-130-100-continuity` adr: `Annual M100 fold-in of quarterly M130 pagos fraccionados` | (**status:** `accepted`)

## Problem Statement

The annual Modelo 100 must fold in the quarterly Modelo 130 pagos fraccionados the filer paid through the year. The plan surfaced that this fold-in is entangled with the engine's aggregation-mechanism ambiguity (relation vs previous_filing), so it is blocked behind the calculation-engine foundations.

## Decision

Model the M100-from-M130 annual fold-in as a relation feeding the engine's relation channel (the canonical cross-modelo mechanism per the aggregation taxonomy), not as a duplicate previous_filing binding. The work proceeds once the calculation-engine foundations ADRs land.
