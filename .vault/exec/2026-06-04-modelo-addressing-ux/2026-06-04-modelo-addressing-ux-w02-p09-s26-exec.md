---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S26'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P09.S26 export default and ambiguity coverage

Scope:
- `src/aeat/entrypoints/cli/test_modelo_export_verb.py`

## Description

- Cover export defaulting to the current verified-complete pointer.
- Cover export preferring the filed pointer over the current verified-complete pointer.
- Cover export refusal when multiple verified-complete revisions exist without a current/filed pointer.

## Outcome

Export revision selection now has real CLI coverage for the command-specific default rules and ambiguity refusal.

## Notes

- Focused export tests passed.
