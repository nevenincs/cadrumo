---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S28'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P12.S28 natural-key id-type guidance

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_work_id_type_hint.py`
- `src/aeat/locales/en.yml`

## Description

- Enrich work-unit-id versus calculation-revision-id hints with the resolved modelo/year/period.
- Point the common recovery path at natural-key `work calculate` usage.
- Keep exact ids described as advanced escape hatches.

## Outcome

The ID-type hint no longer teaches operators to chain raw ids as the normal workflow.

## Notes

- Focused ID-type hint tests passed.
