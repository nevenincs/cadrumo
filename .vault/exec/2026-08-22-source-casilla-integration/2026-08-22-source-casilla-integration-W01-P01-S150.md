---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:a25800f6593d62c238057df854260fb0ce27404cec34ae94821bb094e947548d'
step_id: 'S150'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# migrate every calculation-source provenance constructor, serializer, merge, and revision-identity payload without defaults, aliases, or dual-read compatibility

## Scope

- `src/cadrumo/application`
- `src/cadrumo/adapters`
- `src/cadrumo/domain`

## Description

- Migrate every production provenance constructor to the required lineage fields.
- Project the complete graph through persistence, CLI payloads, revision hashes, and event trace digests.
- Remove the retired provenance fields without aliases, defaults, or dual readers.
- Extend encrypted-load rejection coverage for every required identity axis.

## Outcome

All production constructors and serialization boundaries use the single canonical provenance shape; legacy payload omissions are rejected.

## Notes

Implemented in shared-worktree commit `31e504c55b`; the shared-commit incident described by S149 applies.
