---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:2d2a10e6056dff67ee0383ed99049dc6cb69c14d4b1a882f1f72bc2a15a5ad27'
step_id: 'S101'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Repoint the two application/modelo files reading filing contracts off the package object, which the reachability gate caught as an AttributeError that only fires when the path runs

## Scope

- `src/cadrumo/application/modelo/`

## Changes

- `M` `src/cadrumo/application/modelo/_export.py`
- `M` `src/cadrumo/application/modelo/_revision_replay_inputs.py`
- `verify:` `pytest src/cadrumo/tests/test_namespace_attribute_reachability.py -n 0 -m ""` -> `pass`
