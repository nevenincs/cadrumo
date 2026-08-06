---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:791f74c3c3b3a67fcb3ab70cd7d2d92d5fa35773b345d33ac3585a0a38a47fe8'
step_id: 'S27'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P12.S27 exact-id escape hatches

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_id_type_hint.py`

## Description

- Preserve positional work-unit ids for commands that already accepted exact work-unit addressing.
- Preserve positional calculation-revision ids for exact revision lookup, verify, file, and export escape hatches.
- Route exact ids supplied with natural flags through selector contradiction checks.

## Outcome

Raw ids remain available for advanced exact addressing while natural keys are the common operator path.

## Notes

- Focused ID-type hint tests passed.
