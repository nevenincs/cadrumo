---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S66'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W04.P05.S66 CLI guidance coverage

Scope:
- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`
- `src/aeat/entrypoints/cli/test_modelo_projection.py`

## Description

- Added assertions that saved-calculation guidance lists revisions through modelo/year/period.
- Added project refusal coverage for no Modelo 130 units and no Modelo 130 calculation revisions.

## Outcome

Focused CLI tests now guard the retired raw-ID routing guidance.
