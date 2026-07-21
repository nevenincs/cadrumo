---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S02'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Lock the complete runtime dependency closure after metadata changes

## Scope

- `uv.lock`

## Description

- Resolve the project graph after making both corpus companions mandatory.
- Remove the obsolete `corpus-sources` extra from the locked metadata.
- Retain exactly one unconditional root requirement for each in-repository companion.

## Outcome

The lock records both data distributions as direct runtime dependencies of `cadrumo`
and retains their local development source mappings. It contains no optional-extra
duplicate, so default, agent, and all-extra resolution share one complete tax-work
cohort.

## Notes

`uv lock --check` passed. `uv tree --package cadrumo --depth 1` showed both companions
in the base dependency closure, and direct TOML inspection proved one unconditional
locked requirement for each companion with no `corpus-sources` optional group.
