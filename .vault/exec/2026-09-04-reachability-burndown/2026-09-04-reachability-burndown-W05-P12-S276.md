---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:54c9213519896ddf3ea77defa1805060800937d4e71b23d9541fbbb2e24ba5e1'
step_id: 'S276'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only Modelo edit mutation-capability projection, its request/row/result DTOs, and tests because it hard-codes an UNMEASURED future-operation disposition in production; retain executable edit admission, parsing, preflight, and guarded mutation behavior, update cadence, and remeasure exact reachability.

## Scope

- `Modelo edit services`
- `models`
- `and focused integration tests`

## Changes

- `M` `src/cadrumo/application/modelo/edit_services.py`
- `M` `src/cadrumo/application/modelo/edit_models.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_contract.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_models.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact symbol search for deleted projector and DTOs -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` focused edit integration suites -> `16 passed`
- `verify:` exact reachability -> `265 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

The removed production projection could only return an empty set or one hard-coded `UNMEASURED` calculate row whose reconsideration text described future registration. Its only callers were tests. The executable edit admission, parsing, preflight, and guarded mutation mechanisms remain and pass their real integration behavior. Exact unused symbols improved from 266 to 265.
