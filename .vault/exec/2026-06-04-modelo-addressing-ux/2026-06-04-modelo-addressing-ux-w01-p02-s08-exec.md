---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S08'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P02.S08 revision selector operations

Scope:
- `src/aeat/application/modelo/_selectors.py`

## Description

- Add calculation revision selector enum, selection result, and revision candidate metadata.
- Add current, latest-draft, latest-verified, filed, and explicit revision selection under one work unit.
- Add command-specific current draft, current verified, and exportable selector helpers.
- Add selector refusals for missing, wrong-state, and ambiguous revision selections.

## Outcome

The application selector boundary now models command-specific revision defaults without a generic latest fallback.

## Notes

- New selector errors were registered in the application error-code registry.
