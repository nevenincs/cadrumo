---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:8d5bbf9f063960bbc770d4bf8652e7b65a7327b27826372dc1c9cf888ad607d3'
step_id: 'S343'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Consolidate storage-taxonomy alias behavior at its core owner and delete duplicate adapter and source-literal inventories.

## Scope

- `storage taxonomy tests`
- `namespace taxonomy consumer test`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry_taxonomy_consumer.py`
- `M` `src/cadrumo/core/tests/test_storage_taxonomy_name_unification.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/tests/test_storage_taxonomy_name_unification.py src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/tests/test_storage_taxonomy_name_unification.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
