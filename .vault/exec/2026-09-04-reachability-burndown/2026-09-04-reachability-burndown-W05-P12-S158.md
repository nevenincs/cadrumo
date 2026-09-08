---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:5ec95202b68a5db4805bb2d22e5c8060beddc6b7ab8b5b75b0d90d3eeca26056'
step_id: 'S158'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the remaining test-only profile-custody directory and profile-data directory aliases exposed by removal of the bidirectional taxonomy re-export census, retaining only names that construct live storage grammars.

## Scope

- `storage path definitions`
- `taxonomy-consumer tests`
- `live unused-symbol detector`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/storage_path_definitions.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry_taxonomy_consumer.py`
- `verify:` `uv run ruff check <S158 paths>` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry_taxonomy_consumer.py` -> `pass` (16 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (368 exact symbols, down from 370; 20 orphaned test modules unchanged)
