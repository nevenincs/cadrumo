---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:96db5a8c9815c0f7a88b7f77aacd2bad31fa81882005f7ac4f6e8cb577e0ab6f'
step_id: 'S382'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Add global workbench search and command-palette providers that route stable result and action identities to admitted destinations

## Scope

- `src/cadrumo/entrypoints/tui/search.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/search.py`
- `A` `src/cadrumo/entrypoints/tui/tests/test_search.py`
- `verify:` `uv run pytest -q src/cadrumo/entrypoints/tui/tests/test_search.py` -> `pass`

## Notes

Duplication evidence is unavailable: the project scanner exceeded its 20-second internal timeout on two attempts.
