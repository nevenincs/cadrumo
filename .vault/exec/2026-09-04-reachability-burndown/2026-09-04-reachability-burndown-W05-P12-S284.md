---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:46071d99bf0b3fbb7f826b2f712dc3f8a49ba93ad7e517efe2a8a0f519faf1d4'
step_id: 'S284'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the zero-caller wizard persist-answers facade and its unreachable error/locale vocabulary while retaining the live command writer, shared mode type, projections, and patch owner; rename misleading serialization coverage, run focused gates, update cadence, and remeasure exact reachability.

## Scope

- `wizard persistence module`
- `focused tests`
- `and application locales`

## Changes

- `M` `src/cadrumo/application/wizard/persistence.py`
- `M` `src/cadrumo/application/wizard/tests/test_setup_runtime.py`
- `M` `src/cadrumo/application/wizard/tests/test_persistence_canonical.py`
- `M` `src/cadrumo/locales/ca/application.yml`
- `M` `src/cadrumo/locales/en/application.yml`
- `M` `src/cadrumo/locales/es/application.yml`
- `M` `src/cadrumo/locales/hu/application.yml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for persist-answers facade/error vocabulary -> `no production matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` wizard persistence/runtime tests -> `36 passed`
- `verify:` exact reachability -> `257 unused symbols, 31 unreachable modules, 0 orphaned tests`
