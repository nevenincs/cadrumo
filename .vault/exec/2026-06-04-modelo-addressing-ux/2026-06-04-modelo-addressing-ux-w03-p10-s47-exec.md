---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:5d8fd26cc34e4a43080f8177b65f7394c80100dd103d6350ce8bf1dae7c4bedc'
step_id: 'S47'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P10.S47 work compare-taxation addressing

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Classify `work compare-taxation` as natural-key enrolled for active Modelo 100 work units.
- Confirm the command resolves through the shared work selector before calling the taxation comparison service.
- Preserve exact work-unit id compatibility for advanced historical comparisons.

## Outcome

`work compare-taxation` follows the same visible-target addressing rule as other work-unit commands.

## Notes

- No separate fixture was added because the command's comparison prerequisites are Modelo 100-specific; selector enrollment is covered by shared helper use and adjacent command tests.
