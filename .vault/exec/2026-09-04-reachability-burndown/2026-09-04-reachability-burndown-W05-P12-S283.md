---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:7e8eae65b645946bda86279498892f662138da430378b3ed61bcdd19f07da254'
step_id: 'S283'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the zero-caller speculative censo unadopted-evidence projector, its fixed field/namespace census, parser adapter, exports, and development-staging prose while retaining the live reviewed-censal divergence owner; run focused integration gates, update cadence, and remeasure exact reachability.

## Scope

- `cotejo apply production surface and reviewed-censal integration tests`

## Changes

- `M` `src/cadrumo/application/user_profile/cotejo_apply.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for speculative censo projector/census/namespace symbols -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` reviewed-censal and schema-judgement integration tests -> `14 passed`
- `verify:` exact reachability -> `258 unused symbols, 31 unreachable modules, 0 orphaned tests`
