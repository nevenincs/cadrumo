---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S17'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# open a research note for the M130 agrarian estimación-objetiva classification axis distinguishing agrarian-objetiva from actividad-directa income before binding casilla 08

## Scope

- `.vault/research/`

## Description

Opened the research note scoping the M130 agrarian estimación-objetiva income
classification axis (the prerequisite before casilla 08 "Volumen de ingresos del
trimestre" can be ledger-aggregated). The note records why casilla 08 is not a
bounded mirror (the transaction model carries no agrarian-objetiva marker, so
reusing the estimación-directa income aggregator would mis-route income into the
wrong régimen's casilla) and what is needed (a per-transaction activity-régimen
marker set at classification, validated at preflight), after which casilla 08
becomes a bounded mirror.

Artifact: `.vault/research/2026-06-20-silent-zero-base-aggregation-research.md`.

## Outcome

Research note written and indexed; the agrarian axis is now a recorded ADR-scale
prerequisite so no future agent naively reuses the directa income aggregator for
casilla 08. No code change.

## Notes

This Step is a research deliverable, not a code fix; the agrarian aggregation
itself is deferred until the classification axis lands.
