---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S13'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P02.S13 exportable revision preference coverage

Scope:
- `src/aeat/application/modelo/test_export.py`

## Description

- Add export selector coverage proving a current draft blocks fallback to an older verified revision.
- Cover filed and current verified exportable preference in selector tests.
- Keep export defaults explicit and command-specific instead of selecting arbitrary latest revisions.

## Outcome

Exportable revision selection now refuses unsafe draft-conflict fallback and has focused regression coverage before CLI export wiring.

## Notes

- Focused export selector test passed.
