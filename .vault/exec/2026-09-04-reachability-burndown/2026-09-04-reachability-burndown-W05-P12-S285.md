---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:7a9ca31b8eeffc1e60ae17ba7e234369dc4913a96ae470f8e2107938db46ce2a'
step_id: 'S285'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the zero-caller workflow draft/submission adapters and private bridge, then burn the exposed test-only default-engine factory, missing-adapter errors/locales, hardened-error census rows, and factory tests while retaining the live deadline adapter; run focused gates, update cadence, and remeasure exact reachability.

## Scope

- `workflow adapters`
- `adapter tests`
- `hardened locale test`
- `submission prose`
- `and application locales`

## Changes

- `M` `src/cadrumo/application/workflow/adapters.py`
- `D` `src/cadrumo/application/workflow/tests/test_adapters.py`
- `M` `src/cadrumo/domain/submission/engine.py`
- `M` `src/cadrumo/core/tests/test_locale_coverage_hardened_errors.py`
- `M` `src/cadrumo/locales/ca/application.yml`
- `M` `src/cadrumo/locales/en/application.yml`
- `M` `src/cadrumo/locales/es/application.yml`
- `M` `src/cadrumo/locales/hu/application.yml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for dead adapter/factory/error vocabulary -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` workflow engine and hardened-locale tests -> `10 passed`
- `verify:` exact reachability -> `254 unused symbols, 31 unreachable modules, 0 orphaned tests`
