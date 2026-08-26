---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5c6c1b969f98f8a0757ff0e9a6222a3c72ebf8cf777bcb3dadc31b69affba50f'
step_id: 'S179'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
