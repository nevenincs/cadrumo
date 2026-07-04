---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S22'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Wire the split-install smoke lane into the just packaging-smoke recipe set

## Scope

- `justfile`

## Description

- Add the `packaging-smoke-split` recipe to `justfile`, running `dev.packaging.smoke_split_install`.
- Wire the new recipe into the umbrella `packaging-smoke` recipe, between the extras lane and the browser lane.
- Commit `5fff07ade7`.

## Outcome

- The split-install proof is now a standing packaging gate, run as part of `just packaging-smoke`.

## Notes

Executed inline by the coordinator. No incidents.
