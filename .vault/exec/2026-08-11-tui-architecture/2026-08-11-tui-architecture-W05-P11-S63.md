---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:57761055c49dfde5bba8c5fbe48b73c2543b4a9741bfbbfa5f559e2077bf5334'
step_id: 'S63'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Render only registered safe REVIEW projections and separately response-authorized APPLY and REJECT controls, treating public INPUT and CHOICE interaction kinds as unsupported until a later accepted contract enrolls them

## Scope

- `src/cadrumo/entrypoints/tui/operations/interactions.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/operations/interactions.py`
