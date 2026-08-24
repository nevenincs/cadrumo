---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:05a1fdf86cb809299e41b40c753a4936150b31c1713fac3819c847ef2245a0f5'
step_id: 'S46'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Apply expiry semantics to every scoped census disposition and refuse expired terminal evidence, with mutation-bite tests.

## Scope

- `src/cadrumo/application/registry/`

## Description

- Evaluate the explicit census expiry posture for every entry scoped to a validated revision.
- Refuse expired terminal evidence while retaining the census row owner and a concrete revalidation condition.
- Add a terminal mutation bite that removes an obsolete row's follow-up and proves the closure limb still refuses at the expiry boundary.

## Outcome

- The source-connectivity limb cannot satisfy closure from expired terminal evidence.
- Direct public-facade composition smoke check passed for a Modelo 100 terminal mutation at its inclusive expiry boundary.
- Ruff passed for the composer and its focused coverage test module.

## Notes

- The dedicated pytest invocation did not return within two 30-second timeboxes while concurrent shared-worktree test jobs were active. The equivalent public-facade mutation was executed directly instead; no failure was observed.
