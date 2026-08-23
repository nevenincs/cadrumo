---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:4e6a841f87f49aea4cbb82d0899dea41714d7f8b4ff80111d6cbbcad5be840ac'
step_id: 'S152'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# classify the M720 foreign-asset composite as grounding-blocked until a typed unique resolved-asset identity or separately approved uniqueness-enforced key exists

## Scope

- `src/cadrumo/application/aggregation`
- `.vault`

## Description

- Remove foreign-asset provenance that promoted upstream carrier identifiers to resolved-asset identities.
- Retain calculation outputs while refusing a fabricated primary.
- Preserve M720's grounding-blocked classification pending a typed unique asset identity.

## Outcome

Foreign-assets calculation remains available, but connectivity admission can no longer pass using an ungrounded synthetic identity.

## Notes

Implemented in shared-worktree commit `31e504c55b`. No composite key or weakened identity rule was introduced.
