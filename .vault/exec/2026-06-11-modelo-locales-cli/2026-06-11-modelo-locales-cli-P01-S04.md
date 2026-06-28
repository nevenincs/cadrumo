---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S04'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P01.S04 implement registry-backed schema key inventory

Scope: `src/aeat/locales/_modelo_manager.py`.

## Description

- Add registry-loader-backed modelo loading to the locale manager.
- Add revision id discovery for directory-mode modelos.
- Add inventory derivation for revision-local casilla translation keys.
- Add inventory derivation for modelo-wide continuity translation keys.

## Outcome

The manager can derive required schema-local translation keys from actual registry casillas. Revision-local entries use `casilla_id`, while modelo-wide entries use `continuidad_id` and deduplicate repeated continuity concepts across selected revisions.

## Notes

Focused verification passed for committed M130 and M303 casilla-key inventory plus a temporary real-loader registry proving continuity-key inventory. M100 and M200 currently fail inside the existing registry loader because of unrelated registry validation errors in the active worktree; no schema locale TOML was edited.
