---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:83ddf6161db81dcd4d6a3fcb1e94479e913f66351b4d0e3b5a1acb20cafa553f'
step_id: 'S149'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# define the canonical primary/contributor lineage role and replace the calculation-source provenance shape atomically with separate resolved and contributor axes

## Scope

- `src/cadrumo/core`
- `src/cadrumo/domain/modelos`

## Description

- Add the closed `CalculationSourceLineageRole` vocabulary at the shared core boundary.
- Replace persisted provenance with explicit resolved-source, contributor, role, reference, parent, and fingerprint axes.
- Make every lineage axis participate in calculation revision identity.
- Reject illegal primary parents, missing contributor parents, duplicate primary references, and orphaned edges.

## Outcome

The canonical application and domain carriers now express direct and composite source graphs without conflating resolver ownership with upstream taxonomy.

## Notes

Implemented in shared-worktree commit `31e504c55b`. A local follow-up makes graph validation run for merged composite resolutions too. That shared commit also contains unrelated concurrent registry tests; no peer changes were reverted.
