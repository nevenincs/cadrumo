---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:c8df4a50b4606cf7fa5a164b9e86fe9078433b47ac17b738ed7ab959f0e74c12'
step_id: 'S146'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# make calculation-route ownership validation refuse renamed resolvers, invented pseudo-owners, and stage drift

## Scope

- `src/cadrumo/application/modelo`

## Description

- Anchor each resolver class to an independent canonical production stage specification.
- Validate resolver identifiers and owned sources against the live resolver class attributes.
- Restrict resolver-free ownership to the exact sole manual-input pseudo-owner.
- Refuse invented resolver types, renamed identities, source mutations, typed manual owners, and stage drift.
- Exercise every production resolver with an independent wrong-stage mutation.

## Outcome

Calculation-route validation now proves the supplied ownership rows are the canonical production declaration rather than merely a complete source partition. Resolver-backed rows cannot change class identity, identifier, sources, or stage, and resolver-free rows can only represent the exact manual-input owner.

## Notes

The runtime consumption assertions remain unchanged and continue to resolve against the validated public production route.
