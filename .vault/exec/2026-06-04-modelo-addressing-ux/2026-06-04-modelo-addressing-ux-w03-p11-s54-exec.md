---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S54'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P11.S54 adjacent command regression coverage

Scope:
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`
- `src/aeat/entrypoints/cli/test_modelo_work_id_type_hint.py`

## Description

- Cover adjacent work command natural-key enrollment for rename, revision, history, and discard.
- Cover reconcile command natural-target help surfaces.
- Cover exact-ID type hints redirecting to natural-key guidance.

## Outcome

Adjacent command decisions are pinned by focused CLI regression tests.

## Notes

- Focused W03 tests passed.
