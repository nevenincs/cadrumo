---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S05'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P02.S05 - legacy root private import baseline

Scope: add a frozen private import baseline for the legacy modelo CLI root.

## Description

- Add a static architecture guard for private backend imports in `_modelo.py`.
- Freeze the current private domain modules as allowed legacy debt.
- Allow the debt to shrink while refusing newly introduced private application or domain module imports.

## Outcome

`test_legacy_modelo_root_does_not_add_private_backend_imports` now protects the legacy root. It permits only the current private domain import modules and fails if future edits add new private backend bypasses while decomposition is underway.

## Notes

Verification: `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py -q` passed.
