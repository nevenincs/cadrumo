---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S23'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P09.S23 natural-key modelo export

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_modelo_export_verb.py`

## Description

- Confirm `modelo export` resolves exact and natural filing targets through the shared revision selector.
- Preserve the command-specific export default of filed pointer first, then current verified-complete revision.
- Cover natural-key export of the current verified-complete pointer.

## Outcome

Operators can export a verified modelo through modelo/year/period without copying work-unit or calculation-revision ids.

## Notes

- Focused export tests passed.
