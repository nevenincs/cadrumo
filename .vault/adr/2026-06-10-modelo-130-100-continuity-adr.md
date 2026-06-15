---
tags:
  - '#adr'
  - '#modelo-130-100-continuity'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-10-modelo-130-100-continuity-research]]'
---

# `modelo-130-100-continuity` adr: `Annual M100 fold-in of quarterly M130 pagos fraccionados` | (**status:** `accepted`)

## Problem Statement

The annual Modelo 100 must fold in the quarterly Modelo 130 pagos fraccionados the filer paid through the year. The plan surfaced that this fold-in is entangled with the engine's aggregation-mechanism ambiguity (relation vs previous_filing), so it is blocked behind the calculation-engine foundations.

## Decision

Model the M100-from-M130 annual fold-in as a relation feeding the engine's relation channel (the canonical cross-modelo mechanism per the aggregation taxonomy), not as a duplicate previous_filing binding. The work proceeds once the calculation-engine foundations ADRs land.

## Status

Accepted.
