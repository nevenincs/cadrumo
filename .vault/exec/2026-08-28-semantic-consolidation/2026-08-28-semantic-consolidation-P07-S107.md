---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c41615e6142d98d515febcedac02a9d51bb1d87fe5ef93b88b441e60eb9ff679'
step_id: 'S107'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Publicise the censo parser and repoint the portals service tests, the last names reached through namespaces already made inert

## Scope

- `src/cadrumo/adapters/inbound/censo/`
- `src/cadrumo/application/portals/`

## Changes

- `R` `src/cadrumo/adapters/inbound/censo/_parser.py -> parser.py`
- `M` 14 censo consumers
- `M` `src/cadrumo/application/portals/tests/test_service.py`
- `M` `src/cadrumo/application/portals/tests/test_portal_refusal_message_key_only.py`
- `M` `src/cadrumo/entrypoints/operation_composition.py`
- `M` `src/cadrumo/entrypoints/tui/profile/tests/test_filed_history_operation_view.py`
- `verify:` `pytest src/cadrumo/application/portals src/cadrumo/adapters/inbound/censo -n 0 -m ""` -> `pass`

## Notes

The censo rename regex was written unscoped and rewrote `_parser` in the
declaracion, borrador and justificante packages too, where that module is still
private. Thirteen files were reverted by resolving each relative import against
the filesystem and restoring the private name only where the private module
actually exists.
