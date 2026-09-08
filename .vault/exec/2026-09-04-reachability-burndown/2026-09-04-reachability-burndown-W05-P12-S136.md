---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:710b780adf4602ca1015c52aacc3e5d0d4975b49e459a04ab2630133a982c414'
step_id: 'S136'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the empty relation source-year allowance registry, its injectable suppression API, reconciliation machinery, and tests so every derived relation coverage gap is returned directly

## Scope

- `relation closure validator and detector tests`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_validate_relation_sources.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_relation_closure.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/_validate_relation_sources.py src/cadrumo/domain/calculations/registry/tests/test_relation_closure.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/domain/calculations/registry/tests/test_relation_closure.py` -> `pass`
