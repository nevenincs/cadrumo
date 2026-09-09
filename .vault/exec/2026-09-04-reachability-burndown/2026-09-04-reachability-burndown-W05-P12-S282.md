---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:e52354ee5dc7ce3cdf08efbf2aa4f0d922808ce926355acb5706758c7b686b2f'
step_id: 'S282'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unreachable portable-profile bundle import facade and its sole-called repository/rebuild helpers, then burn the exposed test-only custody restore slice through application, port, adapter, persistence, and restore-only tests while retaining live export-policy behavior; update cadence and remeasure exact reachability.

## Scope

- `profile bundle and custody carry application/port/adapter surfaces and focused tests`

## Changes

- `M` `src/cadrumo/application/user_profile/bundle.py`
- `M` `src/cadrumo/application/user_profile/custody_carry.py`
- `M` `src/cadrumo/application/user_profile/custody_ports.py`
- `M` `src/cadrumo/adapters/persistence/storage/profile_custody.py`
- `M` `src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py`
- `M` `src/cadrumo/application/user_profile/tests/test_custody_roundtrip.py`
- `D` `src/cadrumo/application/user_profile/tests/test_custody_restore_atomicity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for bundle/custody restore surfaces -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` retained custody export-policy test -> `1 passed`
- `verify:` live bundle export/validation imports -> `pass`
- `verify:` exact reachability -> `259 unused symbols, 31 unreachable modules, 0 orphaned tests`
