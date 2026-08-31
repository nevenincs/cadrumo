---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:b02196e12fe20b4f7e656da31fda9aa38289eed53e1aef9b6dc088666fa94c7c'
step_id: 'S62'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Project only OperationPublicEventPageV1 into bounded live and historical log views, honoring public cursors, replay and resynchronization dispositions, and approved diagnostic references without reading the journal

## Scope

- `src/cadrumo/entrypoints/tui/operations/logs.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/operations/logs.py`
