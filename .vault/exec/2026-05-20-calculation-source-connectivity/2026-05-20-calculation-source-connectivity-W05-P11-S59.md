---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:bab90c88e25882a101be6c0219177ea7e87446b288cc6667d5ec7575170b1f8e'
step_id: 'S59'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Run architecture boundary audit for source mesh directionality

## Scope

- `src/aeat/application/aggregation`

## Description

- Run the architecture-boundary audit for source-mesh directionality via the `domain-not-application` import-linter contract and a grimp runtime import-graph pass over the aggregation surface.

## Outcome

PASS — no finding. The `domain-not-application` contract is KEPT over the full tree (3252 files, 15248 dependencies): no production domain module imports the application layer, so the mesh's hexagonal direction holds — registry resolvers/observation protocols stay in the domain, storage-reading source resolvers + mesh orchestration stay in the application layer. The grimp runtime graph confirms every domain→application edge is a test module / conftest (legitimate cross-layer test wiring), including the three `registry.tests → application.aggregation` edges; zero production directionality violation. Recorded in the campaign closeout audit.

## Notes

Both the import-linter contract and the grimp graph read the import graph, not a registry load, so this axis was unaffected by the concurrent modelo-145 registry churn and ran clean now.
