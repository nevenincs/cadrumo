---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:c140e0ebc9d07734b3b355262b4380666b1c9cbc42a81c81f7cdfcd36b356585'
step_id: 'S311'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the canonical-record encoding AST owner census, its production path/function allowlist, trailing-name heuristics, formatting exemptions, and embedded encoder implementations; retain direct canonical-byte behavior.

## Scope

- `canonical record encoding owner test`
- `focused hashing tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_canonical_record_encoding_owner.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S311.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/tests/test_hashing.py src/cadrumo/core/tests/test_hashing_adoption.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Canonical byte behavior remains covered by 16 focused hashing tests. The deleted ownership census inferred serializer semantics from callable spelling and maintained an explicit production exception; the exact production detector remains red on the wider campaign findings.
