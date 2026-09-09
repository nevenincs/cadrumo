---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:3869247319f7567cf0cac22d701c37196d06ded92682d8b0bbb5a0bfcc4b613a'
step_id: 'S343'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
