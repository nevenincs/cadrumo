---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5d366ea321fc1f20ba342d4140ca3bc6d0f1da31b793f942e09e5050fa557147'
step_id: 'S183'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove censo_modelos remains public with locally defined symbols and direct consumer imports

## Scope

- `src/cadrumo/domain/calculations/registry/censo_modelos.py`

## Changes

- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py -n0` -> `pass`

## Notes

No source change was needed: `src/cadrumo/domain/calculations/registry/censo_modelos.py` already advertises only symbols it
defines, and the registry package binds none of them. What was missing was a
gate holding it to that adjudication, which the reviewed matrix recorded as
`keep_public`.

That gate is `test_keep_public_family.py`, one parameterized proof driven from
the matrix rather than one hand-written test per module, so a later re-export
or package binding reds this row specifically. It reads the AST rather than
each object's `__module__`, because a locally defined `Annotated` alias reports
`typing` and an attribute check would call ten honest modules liars. The gate
was proved to bite by planting a borrowed export and observing the matching
parameter case fail.
