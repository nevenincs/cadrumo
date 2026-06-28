---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S48'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P10.S48 work amend addressing

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Classify `work amend` as an exact filing-record surface for this design.
- Preserve `--from-filing-record` because amendments start from a filed/imported record, not merely a visible work target.
- Leave work/revision pointer behavior to the existing amendment application service.

## Outcome

`work amend` remains outside the natural work-unit selector until a filing-record natural selector is designed.

## Notes

- This is an intentional classification decision; no code change was required.
