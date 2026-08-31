---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:648b148297483f9fbdcd9824d82400eeca390b7c8316c4f3a66bef791c6cc291'
step_id: 'S179'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove authority remains public with locally defined symbols and direct consumer imports

## Scope

- `src/cadrumo/domain/calculations/registry/authority.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_authority.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_authority.py -n0` -> `pass`

## Notes

The module declares no `__all__`, so it advertises nothing it does not
define; the proof asserts that, plus that every locally defined public symbol
is unbound in the registry package namespace. An earlier draft of the proof
flagged RegistryAuthorityGrade, which authority.py imports from core's public
namespace for its own use - borrowing a symbol is not re-exporting one, so the
proof was corrected to test the claim the Step actually makes.
