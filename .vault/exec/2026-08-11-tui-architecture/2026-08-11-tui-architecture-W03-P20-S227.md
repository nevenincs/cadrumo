---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ff5bd68bd473bd40969ee6c0af18392a5e757d9f87bdd29b0fb839316735dd8e'
step_id: 'S227'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retain queries as public only for locally defined contract symbols and direct-import every borrowed owner

## Scope

- `src/cadrumo/domain/calculations/registry/queries.py`

## Changes

- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py -n0` -> `pass`

## Notes

No source change was needed: the hard move from `src/cadrumo/domain/calculations/registry/_queries.py` already
landed and the private module is gone. What was missing was a gate holding it
there, which `test_keep_public_family.py` now does per row - the retired path
must be absent AND unimportable, so a reintroduced private module reds this
row specifically rather than passing for being merely unused.

The surviving owner is asserted from the row's terminal destinations rather
than its `new_path`, because a family that moved out of the registry entirely
leaves a `new_path` nothing occupies.

## Changes (second pass)

- `M` `src/cadrumo/domain/calculations/registry/queries.py`
- `M` `src/cadrumo/application/modelo/tests/test_binding_readiness.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_queries.py src/cadrumo/application/modelo/tests/test_source_mesh_missing_sources.py src/cadrumo/domain/calculations/registry/tests/test_source_enrollment.py -n0` -> `pass (34)`

The first pass recorded that no source change was needed. That was true of the
hard move but not of the row, which also asks that the module stay public only
for what it locally defines. Thirteen of its fourteen exported names were
borrowed from `query_reports`, so it was still a re-export facade. No consumer
reached them through `queries`, and the two locally defined symbols consumers
do import were absent from `__all__`. The export list is now the three local
contract symbols; the borrowed types remain imported because the query methods
return them.

Semantic confirmation used the row's own `rag_query` against vaultspec-rag,
which needed its service environment repaired first. `query_reports.py` is a
neighbouring concept, not a competing owner.

`test_binding_readiness.py` derived its fragment filename from the section
directory name, so underscores reached a loader that requires the kebab-case
numbered-fragment grammar. Fixed. Two of its cases stay red on a separate,
actively-moving peer tightening of the legal-reference format in the same
fixture, which is outside this row.
