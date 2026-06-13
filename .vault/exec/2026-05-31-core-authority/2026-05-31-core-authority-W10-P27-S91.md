---
tags:
  - '#exec'
  - '#core-authority'
step_id: S91
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W10.P27.S91 - bundled_authority() factory eliminates load boilerplate

## Outcome

Introduced `bundled_authority() -> ValidatedRegistryAuthority` in
`domain/calculations/registry/_authority.py`. This factory wraps the repeated
`ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())`
pattern. The result is backed by the existing `_load_authority` `lru_cache`, so
repeated calls within one process incur zero recomputation cost.

Exported `bundled_authority` via `domain/calculations/registry/__init__.py`.

Updated `entrypoints/cli/_config/_google.py` `_load_snapshot()` to call
`_bundled_authority()` instead of the inline boilerplate. Removed now-unused
`bundled_path` and `ValidatedRegistryAuthority` imports from that module.

The third site (`adapters/inbound/declaracion/_parser.py`) uses a parameterised
`root` argument (not always bundled path) and correctly stays as a direct `.load()`
call. The `application/filing/__init__.py` site uses `_resources().modelos.authority`
(the resource-managed authority, not a bare `.load()`) and is correct as-is.

## Commit

`b0d3f2a60` — refactor(registry): W10.P27.S91 - bundled_authority() factory eliminates load boilerplate

## Files touched

- `src/aeat/domain/calculations/registry/_authority.py` — added `bundled_authority()`
- `src/aeat/domain/calculations/registry/__init__.py` — exported `bundled_authority`
- `src/aeat/entrypoints/cli/_config/_google.py` — migrated to `_bundled_authority()`

## Verification

`test_authority.py` (6 tests) and `test_queries.py` (11 tests) pass. 17/17 registry
authority tests green.
