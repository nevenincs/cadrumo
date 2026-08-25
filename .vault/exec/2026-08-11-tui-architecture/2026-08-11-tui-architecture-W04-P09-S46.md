---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d30da3dcd8058f4722f17ce75988eeb86a8eb6c7e4541bc0dac77b2f4400b552'
step_id: 'S46'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Create the narrow TUI package facade and reserve launcher-level exports only

## Scope

- `src/cadrumo/entrypoints/tui/__init__.py`

## Description

- Create the canonical `cadrumo.entrypoints.tui` package marker.
- Keep the root facade import-light and expose no component or feature symbols.
- Verify the facade imports successfully with an empty public export set.

## Outcome

Committed as `782ced53c9` (`feat(tui): add narrow entrypoint facade`).
The launcher-level API remains reserved until the dedicated launcher exists.

## Notes

No production policy, application state, compatibility bridge, or lazy export
map was introduced.
