---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:e072d7295da63ccc8a0d44cea69e16d0f22f22b8005cb8f50f5530bb9f8f9550'
step_id: 'S278'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-only M303 simplified-regime WorkUnit facade and compose its two live owners directly in retained tests; preserve secure-profile loading and canonical composition-to-scope behavior, update cadence, and remeasure exact reachability.

## Scope

- `M303 simplified-regime scope resolver and focused tests`

## Changes

- `M` `src/cadrumo/application/modelo/m303_regimen_simplificado_scope.py`
- `M` `src/cadrumo/application/modelo/tests/test_m303_regimen_simplificado_scope.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for deleted facade -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` focused M303 scope suite -> `6 passed`
- `verify:` exact reachability -> `263 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

The removed facade only checked the Modelo code and chained `active_taxpayer_profile` into `m303_regimen_simplificado_scope_for_profile`; no production caller used it. The retained test now composes those live owners directly and still exercises encrypted profile loading plus all three IVA composition outcomes. Exact unused symbols improved from 264 to 263.
