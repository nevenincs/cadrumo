---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:49966f7a232ef60ec5126fb796b4a2b4a7f2db7cfda6cd9b6e3b6b466d136f5c'
step_id: 'S159'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the orphaned persisted-format classification ledger test and its pinned open-gap count, plus the generic schema-version alias kept alive only by that ledger, while retaining executable compatibility lifecycle and namespace lineage gates.

## Scope

- `persisted-format enrollment ledger test`
- `secure-object namespace versions`
- `compatibility and schema-lineage tests`
- `live reachability detector`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `D` `src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py`
- `verify:` `rg -n "SECURE_OBJECT_SCHEMA_VERSION_V3|CONSTANTS_AWAITING_CLASSIFICATION|CONSTANTS_OUTSIDE_THE_INVENTORY|VERSIONED_FORMAT_IMPLEMENTATIONS|UNVERSIONED_FORMAT_REASONS" src/cadrumo --glob '*.py'` -> `pass` (zero matches)
- `verify:` `uv run ruff check src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py` -> `pass`
- `verify:` `uv run pytest -q <compatibility and schema-lineage focused paths> -x` -> `pass` (32 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (367 exact symbols, down from 368; 19 orphaned test modules, down from 20)
