---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:3c3dbfce7aa0bafe0f7799cd6f2fbe9f765d27b5b63b7622c40e3003ad12b664'
step_id: 'S199'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove formula_runtime_ops remains public with locally defined symbols and direct consumer imports

## Scope

- `src/cadrumo/domain/calculations/registry/formula_runtime_ops.py`

## Changes

- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py -n0` -> `pass`

## Notes

No source change was needed: `src/cadrumo/domain/calculations/registry/formula_runtime_ops.py` already advertises only symbols it
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
