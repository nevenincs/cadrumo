---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:69362d8b428c0a90125c0be9a6b5aeedd4f60eb6a60f6a2c76e1cdf81654d87b'
step_id: 'S157'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-manufactured retired bucket-manifest filename alias and the bidirectional test premise that required every taxonomy member to be re-exported, while retaining canonical taxonomy and retirement proof.

## Scope

- `storage path definitions`
- `taxonomy-consumer tests`
- `namespace retirement test`
- `live unused-symbol detector`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/storage_path_definitions.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry_taxonomy_consumer.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `verify:` `uv run ruff check <S157 paths>` -> `pass`
- `verify:` `uv run pytest -q <taxonomy-consumer file> <two focused namespace tests>` -> `pass` (20 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (370 exact symbols, down from 371; 20 orphaned test modules unchanged)

## Notes

The wider namespace-registry file reached 46 passes before the pre-existing production namespace enrollment failure at `test_every_discovered_production_secure_object_namespace_is_registered`: five discovered namespaces are absent from the current registry. The tests directly governing S157 pass independently.
