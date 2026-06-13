---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S11'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W02.P03.S11 - lifecycle rendering support

Scope: move lifecycle rendering helpers into shared rendering support where they are transport only.

## Description

- Add `work_unit_list_lines` to `_modelo_rendering.py`.
- Reuse existing `work_unit_lines` and `work_unit_payload` helpers from the lifecycle registrar.
- Remove local work-list row rendering from the lifecycle registrar.

## Outcome

Lifecycle commands now use shared rendering helpers for work-unit payloads, work-unit detail lines, and work-unit list rows. The registrar remains focused on parsing CLI input, calling application services, and emitting envelopes.

## Notes

Verification: focused CLI lifecycle tests passed after moving the renderer.
