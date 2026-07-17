---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Run incremental reindex then the widened sweep through the resident service, wrangle through the typed resolution, and land the widened relevance mapping as a reviewed committed diff

## Scope

- `src/cadrumo/_data/terminology/relevance/relevance.json`

## Description

- Run the widened sweep through the resident service (incremental reindex
  first): 112 queries over 49 concepts, 0 failed.
- Review the mapping diff: 335 targets vs 247 (+89 gained, 1 lost - a tail
  legal target on the generic 'declaracion' query whose top-6 is unchanged;
  adjudicated acceptable).
- Land the widened relevance mapping and regenerate the coverage report.

## Outcome

Committed mapping: 112 queries / 335 targets. Coverage after widening:
concepts 49/49, legal 121/555 (21.8 percent, from 11 at wave start),
casillas 22/6330, 143 orphan grounding targets. Every new concept's own
card leads its queries; one ranking note recorded (the bare 'modelo 115'
query surfaces the 180 summary card first, its own card second).

## Notes
