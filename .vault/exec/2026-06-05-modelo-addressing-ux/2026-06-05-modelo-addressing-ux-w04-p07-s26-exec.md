---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S26'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
---

# W04.P07.S26 resume ADR gate

Scope:
- `.vault/adr`
- `.vault/exec/2026-06-05-modelo-addressing-ux`

## Decision

No new ADR is required before implementing natural-key `work resume`.

## Rationale

The implementation does not require hidden state or a new legally meaningful selector axis. It uses the already accepted addressing contract:

- visible filing target: active bucket/profile plus modelo, filing year, and period;
- optional registry revision only as the existing work-unit disambiguator;
- exact work-unit id as an advanced escape hatch;
- exact workflow run id as a workflow persistence escape hatch.

The workflow layer already has a local-only resume gate over exact run ids and a newest-run lookup for `(modelo, workflow_period)`. The planned change is a transport/resolution improvement: centralized modelo addressing resolves the work unit first, then workflow lookup resumes the corresponding newest persisted run.

## Consequence

Implementation may proceed under the accepted `2026-06-04` ADR. If later work proposes hidden resume state, a new selector axis beyond registry revision, or a different ambiguity policy for multiple workflow runs, that must stop for a new ADR.

