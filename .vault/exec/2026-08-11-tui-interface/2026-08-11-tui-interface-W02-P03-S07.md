---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:55806935efa270730b698d18dd41db4656a342191b439cfa7ebf0da1b04a11e4'
step_id: 'S07'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Extend settled widgets with linear stage navigation disclosure groups requirement badges and source-action cards

## Scope

- `src/cadrumo/entrypoints/tui/components/widgets.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/components/widgets.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/components/tests/ -q -m unit` -> `pass`
